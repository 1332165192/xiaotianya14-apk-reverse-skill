import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { BUNDLED_SKILL_RANK } from '@deepseek-ai/dsh-skill'

const PROVIDER_NAME = 'apk-reverse'
const SKILL_BODY_URL = new URL('../SKILL.md', import.meta.url)
const RESOURCE_BASE = { kind: 'directory', path: fileURLToPath(new URL('../', import.meta.url)) }
const DESCRIPTION = '手机端 Android APK 逆向作业规范：解包、jadx 反编译、广告定位与清理、权益逻辑分析、数值修改、重打包签名、真机验证。Mobile APK reverse engineering: decode, patch, repack, sign, verify. Use when the user asks to reverse/decompile/modify an APK, remove ads, analyse entitlements, patch values, rebuild or sign an app.'

const CANDIDATE = {
  name: 'apk-reverse',
  description: DESCRIPTION,
  invocation: { modelInvocable: true, userInvocable: true },
  provider: PROVIDER_NAME,
  source: 'bundled',
  resourceBase: RESOURCE_BASE,
  rank: BUNDLED_SKILL_RANK,
  locator: SKILL_BODY_URL,
}

const provider = {
  name: PROVIDER_NAME,
  list: () => Promise.resolve([CANDIDATE]),
  async get() {
    return { ...CANDIDATE, content: await readFile(SKILL_BODY_URL, 'utf8') }
  },
}

export const name = 'skill-apk-reverse'
export const inject = ['skills']
export function apply(ctx) {
  ctx.skills.registerProvider(() => provider)
}
