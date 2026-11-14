// function_patcher.js — 按类名+方法名替换返回值（快速验证用，不持久）
// 用法: frida -U -f <包名> -l function_patcher.js -P CLASS=com.x.Y -P METHOD=isVip -P RET=true
//   不带 -P 时用下面 TARGETS 列表里的默认配置
var TARGETS = [
  // { cls: 'com.example.User', method: 'isVip', ret: true },
];

function getArg(name, dflt) {
  try {
    var i = Process.argv.indexOf('--' + name);
    if (i >= 0) return Process.argv[i + 1];
  } catch (e) {}
  return dflt;
}
var cls = getArg('CLASS', null), method = getArg('METHOD', null), ret = getArg('RET', null);
if (cls && method) TARGETS.push({ cls: cls, method: method, ret: (ret === 'false' ? false : ret === 'true' ? true : ret) });

Java.perform(function () {
  TARGETS.forEach(function (t) {
    try {
      var C = Java.use(t.cls);
      var overloads = C[t.method].overloads;
      overloads.forEach(function (o) {
        o.implementation = function () {
          console.log('[patch] ' + t.cls + '.' + t.method + ' -> ' + t.ret);
          return t.ret;
        };
      });
    } catch (e) {
      console.log('[patch] failed ' + t.cls + '.' + t.method + ': ' + e);
    }
  });
});
