// dump_dex.js — 内存 DEX dump（扫描 dex magic，输出到 OUT_DIR）
// 思路参考 CreditTone/android-reverse-engineering-skill (Apache-2.0)，重写实现
// 用法: bash scripts/frida/run_frida.sh -s dump_dex.js -p <包名>
// 输出目录需可写：默认 /data/local/tmp（root），也可改 /sdcard/Download
var OUT = '/data/local/tmp';
var MAGIC = '64 65 78 0a 30 33 35 00'; // dex\n035\0
var seen = {};
var outIdx = 0;

function log(m) { console.log('[dex-dump] ' + m); }

function writeDex(base, size) {
  var key = base.toString();
  if (seen[key]) return;
  seen[key] = true;
  try {
    var buf = Memory.readByteArray(base, size);
    var name = OUT + '/dump_' + (outIdx++) + '_' + base.toString(16) + '.dex';
    var f = new File(name, 'wb');
    f.write(buf);
    f.flush();
    f.close();
    log('saved ' + name + ' (' + size + ' bytes)');
  } catch (e) {
    log('write failed at ' + base + ': ' + e);
  }
}

function scan() {
  Process.enumerateRanges('r--').forEach(function (r) {
    try {
      Memory.scan(r.base, r.size, MAGIC, {
        onMatch: function (addr) {
          try {
            var size = Memory.readU32(addr.add(0x20)); // header file_size
            if (size > 0x100 && size < 0x4000000) writeDex(addr, size);
          } catch (e) {}
        },
        onError: function (e) {}
      });
    } catch (e) {}
  });
  log('scan done, files: ' + outIdx + ' -> ' + OUT);
}

Java.perform(function () {
  // 等应用加载完再扫；也可手动 frida -U -n <进程> -e "scan()"
  setTimeout(scan, 3000);
});
