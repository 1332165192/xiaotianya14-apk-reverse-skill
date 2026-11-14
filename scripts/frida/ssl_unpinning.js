// ssl_unpinning.js — 关闭常见证书固定（仅授权测试）
// 用法: bash scripts/frida/run_frida.sh -s ssl_unpinning.js -p <包名>
Java.perform(function () {
  var seen = {};
  function log(m) { console.log('[ssl] ' + m); }

  // 1) OkHttp CertificatePinner
  try {
    var Pinner = Java.use('okhttp3.CertificatePinner');
    Pinner.check.overload('java.lang.String', 'java.util.List').implementation = function () {
      log('CertificatePinner.check bypass'); return;
    };
  } catch (e) {}

  // 2) TrustManager（所有实现）
  try {
    var X509TM = Java.use('javax.net.ssl.X509TrustManager');
    var TMImpls = Java.enumerateLoadedClassesSync();
    TMImpls.forEach(function (n) {
      if (n.indexOf('TrustManager') < 0 || seen[n]) return;
      seen[n] = true;
      try {
        var C = Java.use(n);
        C.checkServerTrusted.implementation = function () { log('checkServerTrusted ' + n); };
        C.checkClientTrusted.implementation = function () { log('checkClientTrusted ' + n); };
      } catch (e) {}
    });
  } catch (e) {}

  // 3) Conscrypt
  try {
    var Conscrypt = Java.use('com.android.org.conscrypt.TrustManagerImpl');
    Conscrypt.verifyChain.implementation = function (chain, anchors) {
      log('Conscrypt verifyChain bypass'); return chain;
    };
  } catch (e) {}

  // 4) HostnameVerifier
  try {
    var HV = Java.use('javax.net.ssl.HostnameVerifier');
    var SSL = Java.use('javax.net.ssl.HttpsURLConnection');
    var Default = Java.use('org.apache.http.conn.ssl.StrictHostnameVerifier');
  } catch (e) {}
  try {
    var HttpsURLConnection = Java.use('javax.net.ssl.HttpsURLConnection');
    if (HttpsURLConnection.setDefaultHostnameVerifier) {
      var Proxy = Java.use('javax.net.ssl.HostnameVerifier');
    }
  } catch (e) {}

  // 5) 常见 OkHostnameVerifier
  try {
    var OkHV = Java.use('okhttp3.internal.tls.OkHostnameVerifier');
    OkHV.verify.overload('java.lang.String', 'java.security.cert.X509Certificate').implementation = function () {
      log('OkHostnameVerifier bypass'); return true;
    };
  } catch (e) {}

  log('loaded');
});
