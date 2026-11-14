// jni_method_trace.js — 追踪 JNI RegisterNatives（native 注册的方法）
// 思路参考 CreditTone/android-reverse-engineering-skill (Apache-2.0)，重写实现
// 用法: bash scripts/frida/run_frida.sh -s jni_method_trace.js -p <包名>
function log(m) { console.log('[jni] ' + m); }

function findExport(mods, keyword) {
  var hits = [];
  mods.forEach(function (m) {
    try {
      Module.enumerateSymbols(m.name).forEach(function (s) {
        if (s.name.indexOf(keyword) >= 0 && s.address) hits.push(s);
      });
    } catch (e) {}
  });
  return hits;
}

function install() {
  var mods = Process.enumerateModules().filter(function (m) {
    return /libart|libnativehelper|libandroid_runtime/i.test(m.name);
  });
  var hits = findExport(mods, 'RegisterNatives');
  if (!hits.length) { log('未找到 RegisterNatives 符号（可能被裁剪/混淆）'); return; }
  hits.forEach(function (s) {
    try {
      Interceptor.attach(s.address, {
        onEnter: function (args) {
          // env, clazz, methods, nMethods
          var count = args[3].toInt32();
          log('RegisterNatives count=' + count);
          var arr = args[2];
          for (var i = 0; i < count && i < 64; i++) {
            try {
              var fnPtr = arr.add(i * Process.pointerSize * 4 + Process.pointerSize * 3).readPointer();
              log('  fn#' + i + ' -> ' + fnPtr);
            } catch (e) {}
          }
        }
      });
      log('hooked ' + s.name);
    } catch (e) { log('attach fail: ' + e); }
  });
}

Java.perform(function () { setTimeout(install, 1500); });
