// dex_dump.js — 内存 DEX 扫描/导出（自研，不依赖 frida-dexdump，无 GPL 代码）
//
// 推荐由 scripts/dex_dump.py 驱动；也可给 frida CLI 独立使用:
//   frida -H 127.0.0.1:27043 -l dex_dump.js -f <package>
//
// 关键事实（v0.6.10 修复）:
//   1) Frida 17 移除了 Memory.readU8/readU32/readByteArray 等顶层读函数，
//      必须改用 NativePointer 方法: ptr.readU8() / ptr.add(off).readU32() / ptr.readByteArray(n)。
//      旧脚本对每个 magic 命中都抛 "TypeError: not a function" 并被 catch 吞掉 → 永远 0 导出。
//   2) 只扫 r-- 会漏掉壳解密后的 DEX：360 壳在 rw- 内存里解密，随后 mprotect 成 r-x。
//      r-- 里能扫到的多数是 APK 中的加密副本（magic/version 明文，file_size=0）。
//      默认扫描 r--, rw-, r-x, rwx（壳会在 rw-/rwx/r-x 之间切换权限）。
//   3) 大 DEX 用二进制通道 send(payload, ArrayBuffer)，不要 hex（体积翻倍、JS 拼串极慢）。
//   4) header 校验用: magic/version/version 结束符/header_size=0x70/file_size 范围/
//      endian_tag=0x12345678/不越出所在 range；最终有效性由 Python 侧 adler32 校验兜底。
'use strict';

var MIN_DEX_SIZE = 0x70;
var MAX_DEX_SIZE = 64 * 1024 * 1024;   // 单文件上限
var MAX_TOTAL_BYTES = 256 * 1024 * 1024; // 单轮发送上限，防极端进程把内存/传输打满
var DEFAULT_PROTECTIONS = 'r--,rw-,r-x,rwx';  // rwx 段很小，补上防止壳在 rw-/rwx/r-x 之间切换时漏扫
var SCAN_CHUNK = 16 * 1024 * 1024;      // 分块扫描，坏页不会废掉整个 range
var MAGIC = '64 65 78 0a';

// 在 start..start+len 内找 dex magic，并校验 header。
// 返回 { fileSize, version, checksum } 或 null。
function parseDexAt(p, range) {
  try {
    var v0 = p.add(4).readU8();
    var v1 = p.add(5).readU8();
    var v2 = p.add(6).readU8();
    if (v0 < 0x30 || v0 > 0x39) return null;
    if (v1 < 0x30 || v1 > 0x39) return null;
    if (v2 < 0x30 || v2 > 0x39) return null;
    if (p.add(7).readU8() !== 0) return null;       // version 字符串以 NUL 结尾
    var fileSize = p.add(0x20).readU32();           // file_size
    var headerSize = p.add(0x24).readU32();         // header_size
    if (headerSize !== 0x70) return null;
    if (fileSize < MIN_DEX_SIZE || fileSize > MAX_DEX_SIZE) return null;
    if (p.add(0x28).readU32() !== 0x12345678) return null; // endian_tag (LE 0x12345678)
    // 允许跨出当前 range：跨内存段的 DEX 交给 emitRange 实读一次，
    // 读得到就收数，读不到计入 crossRangeFail（不再静默丢弃）
    return {
      fileSize: fileSize,
      version: String.fromCharCode(v0, v1, v2),
      checksum: p.add(0x08).readU32()
    };
  } catch (e) {
    return null;
  }
}

function scan(protections, opts) {
  opts = opts || {};
  var maxTotal = opts.maxBytes || MAX_TOTAL_BYTES;
  var stats = {
    protections: protections,
    ranges: 0, matches: 0, candidates: 0, sent: 0, bytes: 0,
    dup: 0, readFail: 0, scanFail: 0, perProt: {}, elapsedMs: 0,
    crossRangeTry: 0, crossRangeOk: 0, crossRangeFail: 0, budgetHit: false
  };
  var seenAddr = {};
  var seenContent = {};   // fileSize:version:checksum → 同一 DEX 多映射只发一次
  var errors = [];
  var t0 = Date.now();
  var protList = protections.split(',').map(function (s) { return s.trim(); }).filter(Boolean);

  function emitRange(r, prot) {
    var size = r.size;
    var hits = 0;
    for (var off = 0; off < size; off += SCAN_CHUNK) {
      var len = Math.min(SCAN_CHUNK, size - off);
      if (off + len < size) len = Math.min(len + (MAGIC.split(' ').length - 1), size - off);
      var start = r.base.add(off);
      var matches;
      try {
        matches = Memory.scanSync(start, len, MAGIC);
      } catch (e) {
        stats.scanFail++;
        continue;
      }
      for (var i = 0; i < matches.length; i++) {
        hits++;
        stats.matches++;
        if (stats.budgetHit) return;
        var addr = matches[i].address;
        var key = addr.toString();
        if (seenAddr[key]) continue;
        seenAddr[key] = true;
        stats.candidates++;
        var hdr = parseDexAt(addr, r);
        if (!hdr) continue;
        var ckey = hdr.fileSize + ':' + hdr.version + ':' + hdr.checksum;
        if (seenContent[ckey]) { stats.dup++; continue; }
        var cross = addr.add(hdr.fileSize).compare(r.base.add(r.size)) > 0;
        if (cross) stats.crossRangeTry++;
        // 硬上限：本文件放不下就停（旧版先发再累加，会多导一个文件）
        if (stats.bytes + hdr.fileSize > maxTotal) {
          stats.budgetHit = true;
          return;
        }
        try {
          var buf = addr.readByteArray(hdr.fileSize);
          if (!buf || buf.byteLength !== hdr.fileSize) {
            stats.readFail++;
            if (cross) stats.crossRangeFail++;
            continue;
          }
          seenContent[ckey] = true;
          send({
            type: 'dex',
            address: key,
            protection: prot,
            size: hdr.fileSize,
            version: hdr.version
          }, buf);
          stats.sent++;
          stats.bytes += hdr.fileSize;
          if (cross) stats.crossRangeOk++;
        } catch (e) {
          stats.readFail++;
          if (cross) stats.crossRangeFail++;
          if (errors.length < 20) errors.push((cross ? '[跨段] ' : '') + key + ': ' + String(e));
        }
      }
    }
    return hits;
  }

  protList.forEach(function (prot) {
    var ranges;
    try {
      ranges = Process.enumerateRanges(prot);
    } catch (e) {
      stats.perProt[prot] = { error: String(e) };
      return;
    }
    var p = stats.perProt[prot] = { ranges: ranges.length, matches: 0 };
    ranges.forEach(function (r) {
      if (stats.budgetHit) return;
      stats.ranges++;
      try {
        p.matches += emitRange(r, prot) || 0;
      } catch (e) {
        stats.scanFail++;
      }
    });
  });

  stats.elapsedMs = Date.now() - t0;
  if (errors.length) stats.errors = errors;
  return stats;
}

var busy = false;

// Python 侧通过 script.exports_sync.scan({protections, maxBytes}) 触发；可重复调用（多轮扫描）。
// 注意：Frida 17 的 recv() 处理器实测只触发一次，所以这里用 RPC exports 而不是 script.post。
rpc.exports = {
  scan: function (options) {
    options = options || {};
    if (busy) throw new Error('scan 已在进行中');
    busy = true;
    try {
      return scan(options.protections || DEFAULT_PROTECTIONS, { maxBytes: options.maxBytes });
    } finally {
      busy = false;
    }
  }
};

// 独立使用（frida CLI 直接加载）时自动跑一轮；由 dex_dump.py 驱动时置 __DSH_DEX_MANAGED。
if (typeof globalThis.__DSH_DEX_MANAGED === 'undefined') {
  setTimeout(function () {
    if (busy) return;
    busy = true;
    try {
      var stats = scan(DEFAULT_PROTECTIONS, {});
      send({ type: 'done', stats: stats });
    } catch (e) {
      send({ type: 'error', message: String(e), stack: e && e.stack ? String(e.stack) : '' });
    } finally {
      busy = false;
    }
  }, 2500);
}
