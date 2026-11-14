// hook_encryption_algo.js — 观察常见加密/编码调用（Cipher / MessageDigest / Base64）
// 用法: bash scripts/frida/run_frida.sh -s hook_encryption_algo.js -p <包名>
function log(m) { console.log('[crypto] ' + m); }
function preview(arr) {
  try {
    var s = '';
    for (var i = 0; i < arr.length && i < 48; i++) s += ('0' + (arr[i] & 0xff).toString(16)).slice(-2);
    return s + (arr.length > 48 ? '…' : '');
  } catch (e) { return '?'; }
}

Java.perform(function () {
  try {
    var Cipher = Java.use('javax.crypto.Cipher');
    Cipher.doFinal.overload('[B').implementation = function (input) {
      var r = this.doFinal(input);
      log('Cipher ' + this.getAlgorithm() + ' in=' + preview(input) + ' out=' + preview(r));
      return r;
    };
  } catch (e) { log('Cipher hook fail: ' + e); }

  try {
    var MD = Java.use('java.security.MessageDigest');
    MD.digest.overload('[B').implementation = function (input) {
      var r = this.digest(input);
      log('Digest ' + this.getAlgorithm() + ' in=' + preview(input));
      return r;
    };
  } catch (e) {}

  try {
    var B64 = Java.use('android.util.Base64');
    B64.encodeToString.overload('[B', 'int').implementation = function (b, f) {
      var r = this.encodeToString(b, f);
      log('Base64 in=' + preview(b));
      return r;
    };
  } catch (e) {}
  log('loaded');
});
