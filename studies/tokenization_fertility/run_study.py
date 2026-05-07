#!/usr/bin/env python3
"""
Tokenization Fertility Study
============================
Compares token efficiency across models for Korean medical transcription.

Models:
  - gpt-5.4-mini     → tiktoken o200k_base  (local, instant)
  - deepseek-chat    → DeepSeek API, prompt_tokens field
  - gemini-2.5-flash → Gemini count_tokens API (free endpoint)

Fertility F = tokens(translation) / tokens(Korean source)
  F > 1 → translation needs MORE tokens than the Korean original
  F < 1 → translation needs FEWER tokens (compression)

Usage:
  pip install -r requirements.txt
  python run_study.py           # run with caching
  python run_study.py --no-cache  # force fresh API calls
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR.parent.parent / ".env"
CACHE_FILE = BASE_DIR / "cache.json"
RESULTS_FILE = BASE_DIR / "results.csv"

load_dotenv(ENV_FILE)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ── Pricing ($ / 1M input tokens, May 2026) ───────────────────────────────────
PRICING = {
    "gpt-5.4-mini": 0.75,
    "deepseek-chat": 0.27,
    "gemini-2.5-flash": 0.15,
}

TARGET_LANGS = [
    ("en", "English"),
    ("es", "Spanish"),
    ("zh-CN", "Chinese"),
]

# ── 100 Korean Phrases (5 clinical categories × 20) ──────────────────────────
# Format: (id, category, korean_text)
PHRASES: list[tuple[int, str, str]] = [
    # ── Medical Terminology (1-20) ────────────────────────────────────────────
    (1,  "medical", "혈압이 정상 범위 내에 있습니다."),
    (2,  "medical", "혈당 수치가 높게 나왔습니다."),
    (3,  "medical", "심전도 검사 결과가 이상 없습니다."),
    (4,  "medical", "폐렴 진단을 받았습니다."),
    (5,  "medical", "췌장염 증상이 나타나고 있습니다."),
    (6,  "medical", "갑상선 기능 저하증을 확인했습니다."),
    (7,  "medical", "류마티스 관절염 치료를 시작하겠습니다."),
    (8,  "medical", "뇌졸중 예방을 위해 항응고제를 처방합니다."),
    (9,  "medical", "백내장 수술 일정을 잡았습니다."),
    (10, "medical", "당뇨병성 망막병증이 진행 중입니다."),
    (11, "medical", "신부전으로 인한 투석이 필요합니다."),
    (12, "medical", "골다공증 예방을 위해 칼슘 보충제를 복용하세요."),
    (13, "medical", "대장 내시경 검사를 예약했습니다."),
    (14, "medical", "담낭 제거 수술을 권장합니다."),
    (15, "medical", "만성 폐쇄성 폐질환 증상이 악화되었습니다."),
    (16, "medical", "알레르기 반응으로 에피네프린을 투여했습니다."),
    (17, "medical", "고지혈증 치료를 위해 스타틴을 처방합니다."),
    (18, "medical", "복부 초음파 검사에서 이상 소견이 발견되었습니다."),
    (19, "medical", "요로 감염 치료를 위해 항생제를 처방합니다."),
    (20, "medical", "근육통과 관절통이 동반됩니다."),
    # ── Patient-Doctor Dialogue (21-40) ──────────────────────────────────────
    (21, "dialogue", "언제부터 이런 증상이 시작되었나요?"),
    (22, "dialogue", "통증의 정도를 1에서 10으로 표현해 주세요."),
    (23, "dialogue", "현재 복용 중인 약이 있으신가요?"),
    (24, "dialogue", "가족 중 심장 질환 병력이 있으신가요?"),
    (25, "dialogue", "식사 후에 증상이 더 심해지나요?"),
    (26, "dialogue", "수면 장애가 있으신가요?"),
    (27, "dialogue", "알레르기 반응을 일으키는 음식이 있나요?"),
    (28, "dialogue", "마지막으로 건강 검진을 받은 게 언제인가요?"),
    (29, "dialogue", "흡연이나 음주 습관이 있으신가요?"),
    (30, "dialogue", "입원이 필요할 것 같습니다."),
    (31, "dialogue", "이 약은 식사와 함께 복용하세요."),
    (32, "dialogue", "2주 후에 다시 내원해 주세요."),
    (33, "dialogue", "수술 전 금식이 필요합니다."),
    (34, "dialogue", "검사 결과가 나오면 바로 연락드리겠습니다."),
    (35, "dialogue", "증상이 호전되지 않으면 응급실에 오세요."),
    (36, "dialogue", "하루에 세 번 약을 복용하세요."),
    (37, "dialogue", "이 부위를 누르면 아프신가요?"),
    (38, "dialogue", "지금 처방전을 발급해 드리겠습니다."),
    (39, "dialogue", "운동을 시작하기 전에 의사와 상담하세요."),
    (40, "dialogue", "식이 조절이 매우 중요합니다."),
    # ── Clinical Descriptions (41-60) ─────────────────────────────────────────
    (41, "clinical", "환자는 3일 전부터 발열과 기침이 시작되었습니다."),
    (42, "clinical", "흉부 X선에서 우하엽에 침윤 소견이 보입니다."),
    (43, "clinical", "혈액 검사 결과 백혈구 수치가 정상보다 두 배 높습니다."),
    (44, "clinical", "수술 후 상처 부위에 감염 징후가 없습니다."),
    (45, "clinical", "환자의 의식 상태가 명료합니다."),
    (46, "clinical", "혈압은 140/90mmHg로 고혈압 범위에 해당합니다."),
    (47, "clinical", "복부 촉진 시 우측 상복부에 압통이 있습니다."),
    (48, "clinical", "하지 부종이 양측으로 관찰됩니다."),
    (49, "clinical", "심박수 120회로 빈맥 상태입니다."),
    (50, "clinical", "신장 기능 검사에서 크레아티닌 수치가 상승했습니다."),
    (51, "clinical", "피부에 홍반성 발진이 나타났습니다."),
    (52, "clinical", "호흡음 청진 시 수포음이 들립니다."),
    (53, "clinical", "뇌 MRI에서 허혈성 변화가 관찰됩니다."),
    (54, "clinical", "수술 부위 봉합이 잘 되어 있습니다."),
    (55, "clinical", "동공 반사가 양측 정상입니다."),
    (56, "clinical", "산소 포화도가 95% 이상으로 유지되고 있습니다."),
    (57, "clinical", "체온이 38.5도로 미열이 있습니다."),
    (58, "clinical", "경부 림프절이 촉진됩니다."),
    (59, "clinical", "소변 검사에서 단백뇨가 검출되었습니다."),
    (60, "clinical", "간 효소 수치가 정상의 세 배 이상입니다."),
    # ── General Conversation (61-80) ──────────────────────────────────────────
    (61, "general", "오늘 날씨가 많이 춥네요."),
    (62, "general", "점심은 드셨나요?"),
    (63, "general", "지금 몇 시예요?"),
    (64, "general", "화장실이 어디에 있나요?"),
    (65, "general", "이름이 어떻게 되세요?"),
    (66, "general", "생년월일을 알려주세요."),
    (67, "general", "주소가 어떻게 되세요?"),
    (68, "general", "연락처를 남겨주세요."),
    (69, "general", "보험 카드를 가지고 계신가요?"),
    (70, "general", "대기 시간이 얼마나 걸리나요?"),
    (71, "general", "접수를 도와드리겠습니다."),
    (72, "general", "잠깐 기다려 주세요."),
    (73, "general", "진료실로 들어오세요."),
    (74, "general", "걱정하지 마세요."),
    (75, "general", "오늘 어디가 불편하세요?"),
    (76, "general", "혼자 오셨나요?"),
    (77, "general", "보호자가 함께 계신가요?"),
    (78, "general", "주차는 어디에 하면 되나요?"),
    (79, "general", "다음 예약은 언제가 좋으세요?"),
    (80, "general", "수납은 저쪽에서 하시면 됩니다."),
    # ── Complex / Multi-clause (81-100) ───────────────────────────────────────
    (81,  "complex", "환자분의 현재 상태를 고려했을 때, 수술보다는 보존적 치료가 더 적합할 것으로 판단됩니다."),
    (82,  "complex", "지난 6개월 동안 체중이 10킬로그램 이상 감소했으며, 지속적인 피로감과 식욕 저하가 동반되고 있습니다."),
    (83,  "complex", "혈당 조절이 제대로 되지 않아 당뇨병성 합병증이 여러 장기에서 나타나고 있습니다."),
    (84,  "complex", "이번 검사 결과를 바탕으로 치료 계획을 전면적으로 수정하고 새로운 약물 요법을 시작하겠습니다."),
    (85,  "complex", "수술 후 재활 치료가 매우 중요하며, 물리치료와 작업치료를 병행할 것을 권장합니다."),
    (86,  "complex", "항암 치료 중 나타나는 부작용을 최소화하기 위해 보조 약물을 함께 처방할 예정입니다."),
    (87,  "complex", "고혈압과 당뇨를 동시에 관리하기 위해서는 생활 습관 개선과 약물 치료를 병행해야 합니다."),
    (88,  "complex", "이 환자는 심한 알레르기 반응으로 응급실에 내원하였으며, 즉각적인 처치가 필요한 상태였습니다."),
    (89,  "complex", "장기 이식 후 거부 반응을 막기 위해 평생 면역 억제제를 복용해야 합니다."),
    (90,  "complex", "다학제 팀 회의를 통해 환자의 전반적인 치료 방향을 결정하기로 하였습니다."),
    (91,  "complex", "복수의 전문의 의견을 종합한 결과, 외과적 개입이 불가피한 것으로 결론이 났습니다."),
    (92,  "complex", "환자가 고령이고 기저 질환이 많아 마취 위험도가 높은 점을 충분히 고려해야 합니다."),
    (93,  "complex", "임상 시험 참여를 원하신다면 동의서에 서명하시고 다음 주에 다시 내원해 주세요."),
    (94,  "complex", "최근 발표된 가이드라인에 따르면 이 질환의 일차 치료로 특정 항생제를 권장하고 있습니다."),
    (95,  "complex", "영상 검사와 조직 검사 결과가 일치하지 않아 추가적인 평가가 필요합니다."),
    (96,  "complex", "수술 중 예상치 못한 출혈이 발생하여 수혈이 필요했으며, 현재는 안정적인 상태입니다."),
    (97,  "complex", "이 약물은 신장 기능이 저하된 환자에서 용량 조절이 반드시 필요합니다."),
    (98,  "complex", "심부전 환자에서 이뇨제 사용 시 전해질 불균형이 발생할 수 있으므로 주기적인 모니터링이 필요합니다."),
    (99,  "complex", "퇴원 후 자가 관리 방법을 충분히 교육받으셨나요?"),
    (100, "complex", "만약 이 치료법이 효과가 없다면, 다음 단계로 생물학적 제제를 고려해 볼 수 있습니다."),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Cache helpers
# ═══════════════════════════════════════════════════════════════════════════════

def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"translations": {}, "tokens": {}}


def save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# Translation  (Google Translate via deep-translator, with JSON cache)
# ═══════════════════════════════════════════════════════════════════════════════

def translate_phrases(
    phrases: list[tuple[int, str, str]],
    langs: list[tuple[str, str]],
    cache: dict,
) -> dict[str, dict[str, str]]:
    """Returns {ko_text: {lang_code: translated_text}}"""
    from deep_translator import GoogleTranslator
    from tqdm import tqdm

    translations: dict[str, dict[str, str]] = cache.setdefault("translations", {})
    total_needed = sum(
        1
        for _, _, ko in phrases
        for lang_code, _ in langs
        if translations.get(ko, {}).get(lang_code) is None
    )

    if total_needed == 0:
        print("  ✓ Translations already cached, skipping API calls.")
        return translations

    print(f"  Translating {total_needed} missing phrases via Google Translate…")
    with tqdm(total=total_needed, ncols=80) as bar:
        for _, _, ko in phrases:
            if ko not in translations:
                translations[ko] = {}
            for lang_code, lang_name in langs:
                if translations[ko].get(lang_code) is not None:
                    continue
                try:
                    result = GoogleTranslator(source="ko", target=lang_code).translate(ko)
                    translations[ko][lang_code] = result
                    bar.set_description(f"{lang_name[:6]}")
                    bar.update(1)
                    # light throttle to avoid hitting rate limits
                    time.sleep(0.15)
                except Exception as exc:
                    print(f"\n  WARNING translate({ko!r} → {lang_code}): {exc}")
                    translations[ko][lang_code] = ko  # fallback: keep original

    save_cache(cache)
    return translations


# ═══════════════════════════════════════════════════════════════════════════════
# Tokenizers
# ═══════════════════════════════════════════════════════════════════════════════

def make_openai_counter():
    """
    gpt-5.4-mini uses the o200k_base encoding (same family as gpt-4o).
    Counts are purely local — no API call needed.
    """
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")

    def count(text: str) -> int:
        return len(enc.encode(text))

    return count


def make_deepseek_counter(cache: dict):
    """
    DeepSeek-V3 via OpenAI-compatible API.
    Sends a completion with max_tokens=1 and reads usage.prompt_tokens.
    A blank-message baseline is subtracted to remove format overhead.
    Results are cached to avoid redundant API calls.
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    token_cache: dict[str, int] = cache.setdefault("tokens", {}).setdefault(
        "deepseek-chat", {}
    )

    # Measure fixed format overhead once (empty user message)
    _BASELINE_KEY = "__baseline__"
    if _BASELINE_KEY not in token_cache:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": ""}],
            max_tokens=1,
        )
        token_cache[_BASELINE_KEY] = resp.usage.prompt_tokens
        save_cache(cache)

    baseline: int = token_cache[_BASELINE_KEY]

    def count(text: str) -> int:
        if text in token_cache:
            return token_cache[text]
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": text}],
            max_tokens=1,
        )
        net = max(0, resp.usage.prompt_tokens - baseline)
        token_cache[text] = net
        save_cache(cache)
        return net

    return count


def make_gemini_counter(cache: dict):
    """
    Gemini 2.5 Flash via count_tokens() — a free endpoint (no generation).
    """
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    token_cache: dict[str, int] = cache.setdefault("tokens", {}).setdefault(
        "gemini-2.5-flash", {}
    )

    def count(text: str) -> int:
        if text in token_cache:
            return token_cache[text]
        resp = model.count_tokens(text)
        n = resp.total_tokens
        token_cache[text] = n
        save_cache(cache)
        return n

    return count


# ═══════════════════════════════════════════════════════════════════════════════
# Study runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_study(
    phrases: list[tuple[int, str, str]],
    translations: dict[str, dict[str, str]],
    counters: dict[str, object],
    langs: list[tuple[str, str]],
) -> list[dict]:
    """
    For every phrase × language × model, count tokens and compute fertility.
    Returns a list of flat records suitable for a DataFrame.
    """
    from tqdm import tqdm

    records = []
    tasks = [
        (pid, cat, ko, lang_code, lang_name, model_name, counter_fn)
        for pid, cat, ko in phrases
        for lang_code, lang_name in langs
        for model_name, counter_fn in counters.items()
    ]

    print(f"\n  Counting tokens ({len(tasks)} combinations)…")
    for pid, cat, ko, lang_code, lang_name, model_name, count_fn in tqdm(tasks, ncols=80):
        translated = translations.get(ko, {}).get(lang_code, ko)

        ko_tokens = count_fn(ko)
        tr_tokens = count_fn(translated)

        fertility = tr_tokens / ko_tokens if ko_tokens > 0 else 0.0
        cost_per_1k_ko_chars = (
            (ko_tokens / max(1, len(ko))) * 1000 * PRICING[model_name] / 1_000_000
        )

        records.append(
            {
                "id": pid,
                "category": cat,
                "model": model_name,
                "target_lang": lang_code,
                "target_lang_name": lang_name,
                "ko_text": ko,
                "translated_text": translated,
                "ko_chars": len(ko),
                "tr_chars": len(translated),
                "ko_tokens": ko_tokens,
                "tr_tokens": tr_tokens,
                "fertility": fertility,
                "ko_chars_per_token": len(ko) / max(1, ko_tokens),
                "tr_chars_per_token": len(translated) / max(1, tr_tokens),
                "cost_per_1k_ko_chars_usd": cost_per_1k_ko_chars,
            }
        )

    return records


# ═══════════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════════

def print_report(df) -> None:
    import pandas as pd
    from tabulate import tabulate

    sep = "─" * 72

    print(f"\n{'═'*72}")
    print("  TOKENIZATION FERTILITY STUDY — Korean Medical Transcription")
    print(f"  {len(df['id'].unique())} phrases · {len(df['target_lang'].unique())} target languages · {len(df['model'].unique())} models")
    print(f"{'═'*72}\n")

    # ── 1. Overall summary per model ──────────────────────────────────────────
    print("1. OVERALL AVERAGE TOKENS (Korean source + each translation)\n")
    summary_rows = []
    for model in sorted(df["model"].unique()):
        mdf = df[df["model"] == model]
        ko_avg = mdf["ko_tokens"].mean()
        for lang_code, lang_name in TARGET_LANGS:
            ldf = mdf[mdf["target_lang"] == lang_code]
            summary_rows.append(
                {
                    "Model": model,
                    "Target": lang_name,
                    "KO avg tok": f"{ko_avg:.1f}",
                    "TR avg tok": f"{ldf['tr_tokens'].mean():.1f}",
                    "Fertility": f"{ldf['fertility'].mean():.3f}",
                    "KO chars/tok": f"{ldf['ko_chars_per_token'].mean():.2f}",
                    "TR chars/tok": f"{ldf['tr_chars_per_token'].mean():.2f}",
                }
            )
    print(tabulate(summary_rows, headers="keys", tablefmt="rounded_outline"))

    # ── 2. Fertility heatmap by category ─────────────────────────────────────
    print(f"\n{sep}")
    print("2. AVERAGE FERTILITY BY CATEGORY (all models combined)\n")
    cat_rows = []
    for cat in sorted(df["category"].unique()):
        cdf = df[df["category"] == cat]
        row = {"Category": cat}
        for lang_code, lang_name in TARGET_LANGS:
            ldf = cdf[cdf["target_lang"] == lang_code]
            row[lang_name] = f"{ldf['fertility'].mean():.3f}"
        cat_rows.append(row)
    print(tabulate(cat_rows, headers="keys", tablefmt="rounded_outline"))

    # ── 3. Fertility by model × language ─────────────────────────────────────
    print(f"\n{sep}")
    print("3. FERTILITY BY MODEL × LANGUAGE\n")
    pivot_rows = []
    for model in sorted(df["model"].unique()):
        mdf = df[df["model"] == model]
        row = {"Model": model}
        for lang_code, lang_name in TARGET_LANGS:
            ldf = mdf[mdf["target_lang"] == lang_code]
            row[lang_name] = f"{ldf['fertility'].mean():.3f}"
        pivot_rows.append(row)
    print(tabulate(pivot_rows, headers="keys", tablefmt="rounded_outline"))
    print("  Fertility < 1.0 → translation is MORE compact in tokens\n")

    # ── 4. Token efficiency (chars / token) ───────────────────────────────────
    print(f"\n{sep}")
    print("4. TOKENIZER EFFICIENCY — Korean chars per token\n")
    eff_rows = []
    for model in sorted(df["model"].unique()):
        mdf = df[df["model"] == model].drop_duplicates(subset=["id", "model"])
        # ko_chars_per_token is the same across lang rows for same phrase+model
        eff_rows.append(
            {
                "Model": model,
                "KO chars/token (avg)": f"{mdf['ko_chars_per_token'].mean():.3f}",
                "KO chars/token (min)": f"{mdf['ko_chars_per_token'].min():.3f}",
                "KO chars/token (max)": f"{mdf['ko_chars_per_token'].max():.3f}",
                "Tokens/100 chars": f"{(100 / mdf['ko_chars_per_token'].mean()):.1f}",
            }
        )
    print(tabulate(eff_rows, headers="keys", tablefmt="rounded_outline"))
    print("  Higher chars/token → fewer tokens needed → lower cost\n")

    # ── 5. Estimated cost per 1 M Korean chars ─────────────────────────────────
    print(f"\n{sep}")
    print("5. ESTIMATED COST — processing 1,000,000 Korean characters\n")
    cost_rows = []
    for model in sorted(df["model"].unique()):
        mdf = df[df["model"] == model].drop_duplicates(subset=["id", "model"])
        avg_chars_per_tok = mdf["ko_chars_per_token"].mean()
        tokens_per_1M_chars = 1_000_000 / avg_chars_per_tok
        cost = tokens_per_1M_chars * PRICING[model] / 1_000_000
        cost_rows.append(
            {
                "Model": model,
                "Input $/MTok": f"${PRICING[model]:.2f}",
                "Tokens per 1M chars": f"{tokens_per_1M_chars:,.0f}",
                "Cost per 1M chars": f"${cost:.4f}",
            }
        )
    print(tabulate(cost_rows, headers="keys", tablefmt="rounded_outline"))

    # ── 6. Bottom-5 and Top-5 highest fertility phrases (KO → EN) ─────────────
    print(f"\n{sep}")
    print("6. OUTLIERS — 5 most / least token-expansive phrases (KO→EN, gpt-5.4-mini)\n")
    base = df[(df["model"] == "gpt-5.4-mini") & (df["target_lang"] == "en")].copy()
    base = base.sort_values("fertility")

    print("  Least expansive (translation COMPRESSES tokens):")
    for _, row in base.head(5).iterrows():
        print(f"  [{row['fertility']:.3f}]  {row['ko_text']}")
        print(f"          → {row['translated_text']}")
        print(f"            KO:{row['ko_tokens']} tok  EN:{row['tr_tokens']} tok")

    print("\n  Most expansive (translation EXPANDS tokens):")
    for _, row in base.tail(5).iterrows():
        print(f"  [{row['fertility']:.3f}]  {row['ko_text']}")
        print(f"          → {row['translated_text']}")
        print(f"            KO:{row['ko_tokens']} tok  EN:{row['tr_tokens']} tok")

    print(f"\n{'═'*72}\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Tokenization Fertility Study")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore existing cache and make fresh API calls",
    )
    parser.add_argument(
        "--skip-deepseek",
        action="store_true",
        help="Skip DeepSeek API calls (use if rate-limited)",
    )
    args = parser.parse_args()

    if args.no_cache and CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print("Cache cleared.\n")

    # ── Validate credentials ──────────────────────────────────────────────────
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not DEEPSEEK_API_KEY and not args.skip_deepseek:
        missing.append("DEEPSEEK_API_KEY")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}")
        sys.exit(1)

    cache = load_cache()

    # ── Step 1: Translate ─────────────────────────────────────────────────────
    print("\n[1/3] Translating phrases…")
    translations = translate_phrases(PHRASES, TARGET_LANGS, cache)

    # ── Step 2: Build tokenizer counters ─────────────────────────────────────
    print("\n[2/3] Initialising tokenizers…")
    counters: dict = {}

    print("  • gpt-5.4-mini  → tiktoken o200k_base (local)")
    counters["gpt-5.4-mini"] = make_openai_counter()

    if not args.skip_deepseek:
        print("  • deepseek-chat → DeepSeek API (prompt_tokens)")
        counters["deepseek-chat"] = make_deepseek_counter(cache)

    print("  • gemini-2.5-flash → Gemini count_tokens API")
    counters["gemini-2.5-flash"] = make_gemini_counter(cache)

    # ── Step 3: Count tokens ─────────────────────────────────────────────────
    print("\n[3/3] Counting tokens…")
    records = run_study(PHRASES, translations, counters, TARGET_LANGS)

    # ── Build DataFrame ───────────────────────────────────────────────────────
    import pandas as pd

    df = pd.DataFrame(records)
    df.to_csv(RESULTS_FILE, index=False, encoding="utf-8")
    print(f"\n  Results saved → {RESULTS_FILE.relative_to(BASE_DIR.parent.parent)}")

    # ── Print report ──────────────────────────────────────────────────────────
    print_report(df)


if __name__ == "__main__":
    main()
