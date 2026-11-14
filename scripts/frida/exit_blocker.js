// exit_blocker.js — 拦截退出/自毁，防被踢
Java.perform(function () {
  function log(m) { console.log('[exit] ' + m); }
  try {
    var Sys = Java.use('java.lang.System');
    Sys.exit.implementation = function (code) { log('System.exit(' + code + ') blocked'); };
  } catch (e) {}
  try {
    var Proc = Java.use('android.os.Process');
    Proc.killProcess.implementation = function (pid) { log('killProcess(' + pid + ') blocked'); };
  } catch (e) {}
  try {
    var RT = Java.use('java.lang.Runtime');
    RT.halt.implementation = function (code) { log('Runtime.halt(' + code + ') blocked'); };
    RT.exit.implementation = function (code) { log('Runtime.exit(' + code + ') blocked'); };
  } catch (e) {}
  log('loaded');
});
