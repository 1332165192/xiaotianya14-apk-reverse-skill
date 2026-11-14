<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/avatar-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="assets/avatar-light.png">
    <img src="assets/avatar-dark.png" alt="apk-reverse" width="140" />
  </picture>
</p>

<h1 align="center">apk-reverse · 手机版逆向skill</h1>
<h3 align="center">Android APK Reverse Engineering Skill</h3>

<p align="center"><em style="font-family: Georgia, serif; font-size: 1.15em; color: #888;">Unpack it, understand it, patch it, prove it works.</em></p>

<p align="center">
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/releases"><img src="https://img.shields.io/github/v/release/xiaotianya14/apk-reverse-skill?label=release&logo=github&style=flat" alt="release"></a>
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/stargazers"><img src="https://img.shields.io/github/stars/xiaotianya14/apk-reverse-skill?style=flat&logo=github" alt="stars"></a>
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/forks"><img src="https://img.shields.io/github/forks/xiaotianya14/apk-reverse-skill?style=flat&logo=github" alt="forks"></a>
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/issues"><img src="https://img.shields.io/github/issues/xiaotianya14/apk-reverse-skill?style=flat&logo=github" alt="issues"></a>
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="license">
  <img src="https://img.shields.io/badge/Android-APK%20%2F%20AAB-3DDC84?logo=android&logoColor=white" alt="android">
</p>

<p align="center">
  <a href="#about">About</a> ·
  <a href="#capabilities">Capabilities</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#layout">Layout</a> ·
  <a href="#docs">Docs</a> ·
  <a href="#verify">Verify</a> ·
  <a href="#contributing">Contributing</a> ·
  <a href="#license">License</a>
</p>

<p align="center">
  🌐 <strong>English</strong> · <a href="README_zh.md">中文</a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.png">
    <img src="assets/banner-dark.png" alt="apk-reverse banner" width="100%">
  </picture>
</p>

<br/>

<a id="about"></a>

## About

> **If you are an AI agent**, open [`SKILL.md`](SKILL.md) and follow its routing, consent and
> patch rules before touching any target.

A practical Android APK reverse-engineering skill for phone-based work. It turns “I have an APK”
into a repeatable loop instead of guessed commands:

```text
APK
  → toolcheck / install_tools        (is the toolchain ready?)
  → decode + manifest_summary        (unpack, decompile, map components)
  → scan_premium / find_api_calls    (find the logic and the ads)
  → patch smali / manifest / .so     (make the smallest change)
  → build_sign                       (repack, align, sign)
  → device verify                    (install, launch, check behaviour)
  → field-journal                    (write down cause → fix)
```

**Why this exists**

- APK tasks need a different playbook from generic coding tasks
- jadx / apktool / Frida / IDA are easy to install but easy to misuse
- Phone-only workflows (proot Ubuntu on ARM64) have their own pitfalls
- The same “why did it crash after repacking?” problems get solved twice

### At a glance

| Version | Scripts | Reference docs | CI | License |
|---:|---:|---:|---|---|
| v0.5.0 | 30 + 12 Frida | 18 | GitHub Actions | MIT |

<p align="center">
  <a href="https://star-history.com/#xiaotianya14/apk-reverse-skill&Date">
    <img src="https://api.star-history.com/svg?repos=xiaotianya14/apk-reverse-skill&type=Date" alt="Star history" width="600">
  </a>
</p>

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="capabilities"></a>

## Capabilities

| Area | What it does |
|---|---|
| Decompilation | jadx sources, apktool resources/smali, smali3, CFR |
| Components & ads | SDK signatures, manifest / layout / resource inspection |
| Logic analysis | paid & entitlement checks, numeric logic, storage (SharedPreferences / SQLite) |
| Patching | smali patches, static fields, native `.so` instruction patches |
| Protection | packers, signature checks, integrity checks |
| Dynamic & network | Frida, objection, mitmproxy, certificate-pinning adaptation |
| Delivery | repack, align, sign, install and verify on device |

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="quick-start"></a>

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

Tool downloads are verified against `scripts/download-sha256.txt` (SHA256); a mismatch aborts
the install, and an unpinned version prints its hash with a warning.

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="usage"></a>

## Usage

- The workflow rules and patch patterns live in [`SKILL.md`](SKILL.md); reference docs under
  [`references/`](references/) explain each step in depth.
- Everything runs in proot Ubuntu on ARM64; a regular Linux machine works too.
- Build a release: `bash scripts/make_release.sh --name apk-reverse --public` → zip + `.sha256`,
  then the extracted copy is re-checked.
- Verify a release: `bash scripts/verify_release.sh <zip>` (reads `.sha256` or `SHA256SUMS`).
- Publish to GitHub: `bash scripts/publish_github.sh --tag v<version> --release`; the token comes
  from `$GITHUB_TOKEN` or `~/.config/dsh-go/github-token` and never enters the repo.

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="layout"></a>

## Repository layout

```text
apk-reverse/
├── SKILL.md          # routing / workflow / patch patterns / rules
├── references/       # topic docs
├── scripts/          # executable tools
├── field-journal/    # reusable problem → cause → fix notes
├── assets/           # banner, icon and social preview images
├── AGENTS.md         # agent activation and consent boundaries
├── SECURITY.md       # trust model and reporting
├── CONTRIBUTING.md
├── CHANGELOG.md
├── VERSION
└── LICENSE           # MIT
```

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="docs"></a>

## Documentation

- [`references/identity-check.md`](references/identity-check.md) — local identity card, no online lookups
- [`references/mobile-toolchain.md`](references/mobile-toolchain.md) — toolchain and installation
- [`references/patch-patterns.md`](references/patch-patterns.md) — smali / manifest / layout patching
- [`references/protection-map.md`](references/protection-map.md) — packers, integrity checks, traffic capture
- [`references/device-verify.md`](references/device-verify.md), [`references/device-control.md`](references/device-control.md) — on-device verification
- [`references/security-audit.md`](references/security-audit.md) — exported components, WebView, secrets
- [`docs/STAGES.md`](docs/STAGES.md) — six-stage workflow: entry, artifacts, gate for each stage
- [`docs/REPORT-TEMPLATE.md`](docs/REPORT-TEMPLATE.md) — analysis report template (conclusion first, evidence chain)
- [`docs/MCP-INTEGRATION.md`](docs/MCP-INTEGRATION.md) — JADX / Ghidra / IDA / Burp MCP integration notes
- [`scripts/frida/README.md`](scripts/frida/README.md) — Frida script library (SSL unpinning, anti-debug, exit blocker, root bypass, Frida hider, return-value patcher)
- [`tests/routing_cases.json`](tests/routing_cases.json) — routing regression cases (CI checks with `scripts/check_routing.py`)
- [`docs/ENVIRONMENTS.md`](docs/ENVIRONMENTS.md) — phone proot vs Termux vs desktop agent, and where this skill fits
- [`references/kotlin-r8-recovery.md`](references/kotlin-r8-recovery.md) — R8/ProGuard obfuscation and Kotlin name recovery
- [`references/api-extraction.md`](references/api-extraction.md) — API / auth headers / third-party host extraction
- [`references/on-device-tooling.md`](references/on-device-tooling.md) — on-device GUI toolchain: MT Manager / NP Manager / LSPosed / Termux vs scripts
- [`references/lsposed-modules.md`](references/lsposed-modules.md) — LSPosed module fallback when repacking is refused
- [`references/decompilers.md`](references/decompilers.md) — decompiler choice: jadx / Fernflower / ddc (with on-phone install)
- [`references/triage-playbook.md`](references/triage-playbook.md) — 15-minute triage checklist
- [`docs/EVIDENCE.md`](docs/EVIDENCE.md) — evidence levels and ledger discipline (`scripts/ledger.py`)
- [`docs/APP-INTEGRATION.md`](docs/APP-INTEGRATION.md) — using this skill inside the phone app
- See the index at the end of [`SKILL.md`](SKILL.md)

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="verify"></a>

## Release integrity

Every release ships a `SHA256SUMS` file (and `<zip>.sha256`); recipients verify with:

```sh
sha256sum -c SHA256SUMS
# or
bash scripts/verify_release.sh apk-reverse.zip SHA256SUMS
```

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="contributing"></a>

## Contributing

Contributions are welcome — issues, better patch patterns, new reference docs, field-journal notes.

1. Fork the repository
2. `git checkout -b feature/your-idea`
3. Commit your change (`git commit -m 'Add your idea'`)
4. `git push origin feature/your-idea`
5. Open a pull request

Please keep changes inside the consent and authorization boundaries described in
[`AGENTS.md`](AGENTS.md) and [`SECURITY.md`](SECURITY.md).

### Contributors

<a href="https://github.com/xiaotianya14/apk-reverse-skill/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=xiaotianya14/apk-reverse-skill" alt="contributors" />
</a>

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="built-with"></a>

## Built with

<p align="left">
  <img src="https://skillicons.dev/icons?i=python,bash,java,nodejs,docker,git,linux&theme=light" /><br/>
  <code>jadx</code> · <code>apktool</code> · <code>Frida</code> · <code>IDA Pro</code> · <code>Ghidra</code>
</p>

<a id="acknowledgments"></a>

## Acknowledgments

Thanks to the open-source tool authors behind jadx, apktool, Frida, radare2, Ghidra and every
tool this skill relies on. This project is a workflow layer on top of their work.

<a id="license"></a>

## License

MIT — see [`LICENSE`](LICENSE). Read the disclaimer below before use.

> **Disclaimer**: this project is for learning/research on applications you **own or are
> authorized to test**. You are responsible for data loss, device damage and legal risk.
> Do not use it against other people's devices, unauthorized apps, or in violation of
> platform terms. No warranty; the authors accept no liability.

<p align="right">(<a href="#about">back to top</a>)</p>
