// dump_so.js — dump 已加载的 .so（按模块写文件）
// 思路参考 CreditTone/android-reverse-engineering-skill (Apache-2.0)，重写实现
// 用法: bash scripts/frida/run_frida.sh -s dump_so.js -p <包名>
var OUT = '/data/local/tmp';
var KEY = 'lib'; // 只 dump 名字里含 lib 的模块；改成 '' 输出全部

function log(m) { console.log('[so-dump] ' + m); }

function dumpModule(m) {
  try {
    if (KEY && m.name.indexOf(KEY) < 0) return;
    var ranges = Process.enumerateRanges('r-x').filter(function (r) {
      return r.file && r.file.path && r.file.path.indexOf(m.name) >= 0;
    });
    if (!ranges.length) return;
    var base = null, end = null;
    ranges.forEach(function (r) {
      if (base === null || r.base.compare(base) < 0) base = r.base;
      var e = r.base.add(r.size);
      if (end === null || e.compare(end) > 0) end = e;
    });
    var size = end.sub(base);
    var buf = Memory.readByteArray(base, size);
    var name = OUT + '/' + m.name + '.' + base.toString(16) + '.so';
    var f = new File(name, 'wb');
    f.write(buf); f.flush(); f.close();
    log('saved ' + name + ' (' + size + ' bytes)');
  } catch (e) {
    log('dump ' + m.name + ' failed: ' + e);
  }
}

function run() {
  Process.enumerateModules().forEach(dumpModule);
  log('done -> ' + OUT);
}
setTimeout(run, 3000);
