// ssl_log.js — 明文记录 TLS 读写（hook libssl 的 SSL_write / SSL_read）
// 用法: bash scripts/frida/run_frida.sh -s ssl_log.js -p <包名>
// 注意：数据量大，建议先过滤目标域名；内容可能含敏感信息，只用于授权测试
function log(m) { console.log('[ssl-log] ' + m); }

function hookSsl(modName) {
  ['SSL_write', 'SSL_read'].forEach(function (fn) {
    var p = Module.findExportByName(modName, fn);
    if (!p) return;
    Interceptor.attach(p, {
      onEnter: function (args) {
        try {
          var len = args[2].toInt32();
          if (len <= 0 || len > 65536) return;
          var s = args[1].readByteArray(len);
          var u8 = new Uint8Array(s);
          var text = '';
          for (var i = 0; i < u8.length && i < 200; i++) {
            var c = u8[i];
            text += (c >= 32 && c < 127) ? String.fromCharCode(c) : '.';
          }
          log(fn + ' len=' + len + ' ' + text);
        } catch (e) {}
      }
    });
    log('hooked ' + modName + '!' + fn);
  });
}

Process.enumerateModules().forEach(function (m) {
  if (/libssl|libboringssl|libcronet/i.test(m.name)) hookSsl(m.name);
});
