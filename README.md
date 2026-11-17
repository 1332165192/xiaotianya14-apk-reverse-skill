<a id="install-dshgo"></a>

## Install in DSH Go / DeepSeek Harness

| Way | Action |
|---|---|
| **DSH Go marketplace** (recommended) | App → Plugins → search `apk-reverse` → install; restart the core |
| **Plugin command** | `dsh plugin --profile web add github:xiaotianya14/apk-reverse-skill` |
| **Manual** | Download the release zip, unzip, `dsh plugin --profile web add <dir>` |

- Skill name: `apk-reverse`. Trigger it by asking to reverse/decode an APK, remove ads, or inspect entitlement logic.
- On a phone you do **not** need adb: DSH Go ships phone-control tools (`screen`, `tap`, `type`, `open`, `key`, `handoff`) for on-device verification.
- Desktop (Linux/WSL) works with the same commands and toolchain.
- **Manual package needs unzipping**: `dsh plugin add` accepts a local directory, an npm package, or `github:owner/repo` — not a zip. Unzip the release package first, then run `dsh plugin --profile web add <unzipped-dir>`. Marketplace and plugin-command installs need no unzip.

### 中文说明（安装到 DSH Go）

| 方式 | 操作 |
|---|---|
| **DSH Go 商城**（推荐） | App → 插件市场 → 搜 `apk-reverse` → 安装；重启内核生效 |
| **插件命令** | `dsh plugin --profile web add github:xiaotianya14/apk-reverse-skill` |
| **手动包** | 下载 Release 的 zip → 解压 → `dsh plugin --profile web add <目录>` |

- 技能名：`apk-reverse`；装好后在对话里说「逆向这个 APK / 去广告 / 看付费逻辑」即可触发。
- 手机端不需要 adb：DSH Go 自带手机操控工具（`screen`/`tap`/`type`/`open`/`key`/`handoff`）可做真机验证。
- 电脑端（Linux/WSL）同样可装，命令与工具链一致。
- **手动包要解压**：`dsh plugin add` 只接受「本地目录 / npm 包名 / github:owner/repo」，不收 zip；所以离线包要先解压成文件夹，再 `dsh plugin --profile web add <那个文件夹>`。商城安装与插件命令都不用解压。
- 商城收录情况：当前已在 **awesome-dsh-plugin** 上架；其他商城尚在审核/抓取中，搜不到时请用上面的「插件命令」或「手动包」。

<p align="right">(<a href="#about">Back to top</a>)</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/avatar-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/avatar-light.svg">
    <img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/avatar-dark.svg" alt="apk-reverse" width="140" />
  </picture>
</p>

<h1 align="center">apk-reverse · 手机版逆向skill</h1>
<h3 align="center">Android APK Reverse Engineering Skill</h3>

<p align="center"><em style="font-family: Georgia, serif; font-size: 1.15em; color: #888;">Unpack it, understand it, patch it, prove it works.</em></p>

<p align="center">
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/releases"><img src="https://img.shields.io/github/v/release/xiaotianya14/apk-reverse-skill?label=version&color=2ea44f" alt="version"></a>
  <a href="LICENSE"><img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/badges/license.svg" alt="license"></a>
  <img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/badges/android.svg" alt="android">
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/actions"><img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/badges/ci.svg" alt="CI"></a>
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
    <source media="(prefers-color-scheme: dark)" srcset="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/banner-dark-v3.webp">
    <source media="(prefers-color-scheme: light)" srcset="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/banner-light-v3.webp">
    <img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/banner-dark-v3.webp" alt="apk-reverse banner" width="100%">
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
| v0.6.2 | 32 + 12 Frida | 24 | GitHub Actions | MIT |

<p align="center">
  ⭐ <a href="https://github.com/xiaotianya14/apk-reverse-skill/stargazers">Star this repo</a> ·
  🍴 <a href="https://github.com/xiaotianya14/apk-reverse-skill/forks">Fork</a> ·
  🐛 <a href="https://github.com/xiaotianya14/apk-reverse-skill/issues">Report an issue</a>
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
- Build a release: `bash scripts/make_release.sh --name apk-reverse --public` → zip（+ 本地 `.sha256`，发布附件只传 `SHA256SUMS`）,
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
- [`references/native-fuzzing.md`](references/native-fuzzing.md) — native fuzzing (AFL++/ASan) feasibility
- See the index at the end of [`SKILL.md`](SKILL.md)

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="verify"></a>

## Release integrity

Every release ships a `SHA256SUMS` file; recipients verify with:

```sh
sha256sum -c SHA256SUMS
# or
bash scripts/verify_release.sh apk-reverse.zip SHA256SUMS
```

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="contributing"></a>


## Contact

- Email: <xiaotianya14@gmail.com>
- QQ Group: **258605008**
- Feedback: [GitHub Issues](https://github.com/xiaotianya14/apk-reverse-skill/issues)

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

<a href="https://github.com/xiaotianya14/apk-reverse-skill/graphs/contributors">Contributors</a> — PRs welcome.

<p align="right">(<a href="#about">back to top</a>)</p>

<a id="built-with"></a>

## Built with

<p align="left">
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

## License & assets

- **Code & docs**: MIT (see [`LICENSE`](LICENSE)).
- **Visual assets are NOT MIT-licensed**: avatars, banners, icon, social image and badge styles in `assets/`
  remain © xiaotianya14, all rights reserved — no commercial use, no redistribution, no relicensing.
- **Private packages** (game-mod material, working notes) are not published and not licensed.
- Third-party tools, SDKs and trademarks remain under their own terms. See [`NOTICE`](NOTICE) for details.

