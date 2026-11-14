// keystore_dump.js — 观察 SharedPreferences 与 KeyStore 读取（密钥/令牌常见落点）
// 用法: bash scripts/frida/run_frida.sh -s keystore_dump.js -p <包名>
function log(m) { console.log('[secrets] ' + m); }

Java.perform(function () {
  try {
    var SP = Java.use('android.app.SharedPreferencesImpl');
    SP.getString.implementation = function (k, d) {
      var v = this.getString(k, d);
      log('SP.getString ' + k + ' = ' + (v ? String(v).slice(0, 80) : v));
      return v;
    };
  } catch (e) { log('SharedPreferences hook fail: ' + e); }

  try {
    var KS = Java.use('java.security.KeyStore');
    KS.getKey.implementation = function (alias, pwd) {
      log('KeyStore.getKey alias=' + alias);
      return this.getKey(alias, pwd);
    };
    KS.aliases.implementation = function () {
      var e = this.aliases();
      var out = [];
      while (e.hasMoreElements()) out.push(String(e.nextElement()));
      log('KeyStore aliases: ' + out.join(','));
      return e;
    };
  } catch (e) {}
  log('loaded');
});
