<p align="center">
  <img src="assets/banner-dark.png" alt="apk-reverse" width="100%" />
</p>

<h1 align="center">apk-reverse · 手机版逆向skill</h1>
<h3 align="center">Android APK Reverse Engineering Skill</h3>

<p align="center">
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/releases"><img src="https://img.shields.io/github/v/release/xiaotianya14/apk-reverse-skill?label=release&logo=github&style=flat" alt="release"></a>
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/stargazers"><img src="https://img.shields.io/github/stars/xiaotianya14/apk-reverse-skill?style=flat&logo=github" alt="stars"></a>
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/forks"><img src="https://img.shields.io/github/forks/xiaotianya14/apk-reverse-skill?style=flat&logo=github" alt="forks"></a>
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/issues"><img src="https://img.shields.io/github/issues/xiaotianya14/apk-reverse-skill?style=flat&logo=github" alt="issues"></a>
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="license">
  <img src="https://img.shields.io/badge/Android-APK%20%2F%20AAB-3DDC84?logo=android&logoColor=white" alt="android">
</p>

<p align="center">
  <strong>English</strong> | <a href="README_zh.md">中文</a>
</p>

> **Disclaimer**: this project is for learning/research on applications you **own or are
> authorized to test**. You are responsible for data loss, device damage and legal risk.
> Do not use it against other people's devices, unauthorized apps, or in violation of
> platform terms. No warranty; the authors accept no liability.

A practical Android APK reverse-engineering skill for phone-based work: unpack, decompile,
analyze code and resources, patch, repack, sign and verify on device. Commands are tested in
proot Ubuntu on ARM64; a regular Linux machine works too.

## Capabilities

- Decompilation: jadx sources, apktool resources/smali, smali3, CFR
- Component and ad analysis: SDK signatures, manifest/layout/resource inspection
- Logic analysis: paid/entitlement checks, numeric logic, storage (SharedPreferences/SQLite)
- Patching: smali patches, static fields, native `.so` instruction patches
- Protection analysis: packers, signature checks, integrity checks
- Dynamic/network analysis: Frida, objection, mitmproxy, certificate-pinning adaptation
- Delivery: repack, align, sign, install and verify on device

## Quick start

```sh
SK=/path/to/apk-reverse

bash $SK/scripts/toolcheck.sh                 # tool check
bash $SK/scripts/install_tools.sh             # install missing tools

bash $SK/scripts/decode.sh app.apk --out ./work   # decode
python3 $SK/scripts/manifest_summary.py ./work    # manifest summary
python3 $SK/scripts/scan_premium.py ./work        # paid/entitlement candidates
python3 $SK/scripts/find_api_calls.py ./work      # API and credential hints
bash $SK/scripts/build_sign.sh ./work out.apk     # repack + sign
```

Tool downloads are verified against `scripts/download-sha256.txt` (SHA256); a mismatch
aborts the install, an unpinned version prints its hash with a warning.

Release: `bash scripts/make_release.sh --name apk-reverse --public` builds the zip, writes
`.sha256`, and re-checks the extracted copy.
Verify a downloaded release: `bash scripts/verify_release.sh <zip>` (uses `.sha256` or `SHA256SUMS`).

Publish to GitHub: `bash scripts/publish_github.sh --repo https://github.com/<you>/apk-reverse.git --tag v0.0.2 --release`.
Token comes from `$GITHUB_TOKEN` or `~/.config/dsh-go/github-token`; it never enters the repo.

## Repository layout

```text
apk-reverse/
├── SKILL.md          # routing / workflow / patch patterns / rules
├── references/       # topic docs
├── scripts/          # executable tools
├── field-journal/    # reusable problem → cause → fix notes
├── AGENTS.md         # agent activation and consent boundaries
├── SECURITY.md       # trust model and reporting
├── CONTRIBUTING.md
├── CHANGELOG.md
├── VERSION
└── LICENSE           # MIT
```

## Documentation

- `references/identity-check.md` — local identity card, no online lookups
- `references/mobile-toolchain.md` — toolchain and installation
- `references/patch-patterns.md` — smali/manifest/layout patching
- `references/protection-map.md` — packers, integrity checks, traffic capture
- `references/device-verify.md`, `references/device-control.md` — on-device verification
- `references/security-audit.md` — exported components, WebView, secrets
- See the index at the end of `SKILL.md`


## 发行包校验

对外分发 zip 时配套 `SHA256SUMS`（或 `<包>.sha256`），接收方执行：

```sh
sha256sum -c SHA256SUMS
# 或
bash scripts/verify_release.sh apk-reverse.zip SHA256SUMS
```

## Release integrity

Distribute the zip with a `SHA256SUMS` file (or `<zip>.sha256`); recipients verify with:

```sh
sha256sum -c SHA256SUMS
# or
bash scripts/verify_release.sh apk-reverse.zip SHA256SUMS
```

## Contributors

<a href="https://github.com/xiaotianya14/apk-reverse-skill/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=xiaotianya14/apk-reverse-skill" alt="contributors" />
</a>

## License

MIT — see [LICENSE](LICENSE). Read the disclaimer above before use.
