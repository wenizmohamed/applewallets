#!/usr/bin/env python3
"""Rebuild ALL 8 Sakina Apple Wallet passes with proper storeCard + strip layout.

Fixes:
- storeCard style (not generic) — strip.png shows the full artwork on pass face
- NO background.png — it confuses storeCard layout and Apple blurs it anyway
- Unique serial numbers every build — kills iPhone Wallet cache
- Signed with real Pass Type ID .p12 cert
"""

import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

# ── paths ──────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
REPO = HERE
WALLET_PASSES = Path("C:/Users/wenim/.kimi/wallet-passes")
PREVIEWS = WALLET_PASSES / "assets" / "client" / "previews" / "previews"
P12 = WALLET_PASSES / "certs" / "sakina_pass_type_id_20260620.p12"
P12_PASSWORD = "3FNZkxG6eCuus3zWUox7B9MuRWGl6m1i"
OUTPUT = REPO / "dist"

# ── card data ──────────────────────────────────────────────────────────
MORNING_TEXT = (
    "اللهم إني أصبحت أشهدك، وأشهد حملة عرشك، وملائكتك، وجميع خلقك، "
    "أنك أنت الله لا إله إلا أنت وحدك لا شريك لك، وأن محمدًا عبدك ورسولك.\n\n"
    "اللهم أنت لا إله إلا أنت، خلقتني وأنا عبدك، وأنا على عهدك ووعدك ما استطعت، "
    "أعوذ بك من شر ما صنعت، أبوء لك بنعمتك علي، وأبوء بذنبي فاغفر لي، "
    "فإنه لا يغفر الذنوب إلا أنت.\n\n"
    "رضيت بالله ربًا، وبالإسلام دينًا، وبمحمد ﷺ نبيًا ورسولًا."
)

EVENING_TEXT = (
    "اللهم إني أمسيت أشهدك، وأشهد حملة عرشك، وملائكتك، وجميع خلقك، "
    "أنك أنت الله لا إله إلا أنت وحدك لا شريك لك، وأن محمدًا عبدك ورسولك.\n\n"
    "اللهم ما أمسى بي من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك، "
    "فلك الحمد ولك الشكر.\n\n"
    "أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، "
    "له الملك وله الحمد وهو على كل شيء قدير."
)

SLEEP_TEXT = (
    "باسمك اللهم أموت وأحيا.\n\n"
    "اللهم أسلمت نفسي إليك، وفوضت أمري إليك، ووجهت وجهي إليك، "
    "وألجأت ظهري إليك، رغبة ورهبة إليك، لا ملجأ ولا منجا منك إلا إليك، "
    "آمنت بكتابك الذي أنزلت وبنبيك الذي أرسلت."
)

WAKING_TEXT = (
    "الحمد لله الذي أحيانا بعد ما أماتنا وإليه النشور.\n\n"
    "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد، "
    "وهو على كل شيء قدير، سبحان الله، والحمد لله، ولا إله إلا الله، "
    "والله أكبر، ولا حول ولا قوة إلا بالله."
)

AFTER_PRAYER_TEXT = (
    "أستغفر الله (ثلاثًا)، اللهم أنت السلام ومنك السلام، تباركت يا ذا الجلال والإكرام.\n\n"
    "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير، "
    "اللهم لا مانع لما أعطيت، ولا معطي لما منعت، ولا ينفع ذا الجد منك الجد."
)

LEAVING_TEXT = (
    "بسم الله، توكلت على الله، ولا حول ولا قوة إلا بالله.\n\n"
    "اللهم إني أعوذ بك أن أضل أو أضل، أو أزل أو أزل، "
    "أو أظلم أو أظلم، أو أجهل أو يجهل علي."
)

RIZQ_TEXT = (
    "اللهم إني أسألك علمًا نافعًا، ورزقًا طيبًا، وعملًا متقبلًا.\n\n"
    "اللهم اكفني بحلالك عن حرامك، وأغنني بفضلك عمن سواك.\n\n"
    "اللهم إني أسألك من فضلك ورحمتك، فإنه لا يملكها إلا أنت."
)

CARDS = {
    "morning":      {"title": "أذكار الصباح",     "body": MORNING_TEXT},
    "morning_alt":  {"title": "أذكار الصباح",     "body": MORNING_TEXT},
    "evening":      {"title": "أذكار المساء",     "body": EVENING_TEXT},
    "sleep":        {"title": "أذكار النوم",       "body": SLEEP_TEXT},
    "waking":       {"title": "أذكار الاستيقاظ",   "body": WAKING_TEXT},
    "after_prayer": {"title": "أذكار بعد الصلاة",  "body": AFTER_PRAYER_TEXT},
    "leaving":      {"title": "دعاء الخروج",       "body": LEAVING_TEXT},
    "rizq":         {"title": "دعاء الرزق",        "body": RIZQ_TEXT},
}

CARD_BOUNDS = (1080, 130, 1760, 960)  # crop the actual wallet card from mockup

# ── signing imports ────────────────────────────────────────────────────
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12, pkcs7
import requests


def sha1(path: Path) -> str:
    import hashlib
    h = hashlib.sha1()
    h.update(path.read_bytes())
    return h.hexdigest()


def write_manifest(pass_dir: Path) -> bytes:
    manifest = {}
    for f in sorted(pass_dir.iterdir()):
        if f.is_file() and f.name not in ("manifest.json", "signature"):
            manifest[f.name] = sha1(f)
    mb = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
    (pass_dir / "manifest.json").write_bytes(mb)
    return mb


def fetch_wwdr():
    r = requests.get("https://www.apple.com/certificateauthority/AppleWWDRCAG4.cer", timeout=20)
    r.raise_for_status()
    return x509.load_der_x509_certificate(r.content, default_backend())


def load_p12(p12_path: Path, password: str):
    data = p12_path.read_bytes()
    private_key, cert, certs = pkcs12.load_key_and_certificates(
        data, password.encode(), default_backend()
    )
    return private_key, cert, list(certs) if certs else []


def sign_manifest(manifest_bytes, private_key, cert, extra_certs, include_wwdr=True):
    builder = pkcs7.PKCS7SignatureBuilder().set_data(manifest_bytes).add_signer(
        cert, private_key, hashes.SHA256()
    )
    for c in extra_certs:
        builder = builder.add_certificate(c)
    if include_wwdr:
        builder = builder.add_certificate(fetch_wwdr())
    return builder.sign(
        serialization.Encoding.DER,
        [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
    )


# ── image helpers ──────────────────────────────────────────────────────

def cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    ratio = max(w / image.width, h / image.height)
    resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def extract_wallet_card(src: Path) -> Image.Image:
    """Crop the actual Wallet card from the mockup (left panel = explanation)."""
    image = Image.open(src).convert("RGB")
    ref_w, ref_h = (1840, 1114)
    if image.width < ref_w or image.height < ref_h:
        raise ValueError(f"Unexpected size for {src.name}: {image.size}")
    sx = image.width / ref_w
    sy = image.height / ref_h
    box = (
        round(CARD_BOUNDS[0] * sx),
        round(CARD_BOUNDS[1] * sy),
        round(CARD_BOUNDS[2] * sx),
        round(CARD_BOUNDS[3] * sy),
    )
    return image.crop(box)


def make_strip_images(card: Image.Image, out_dir: Path):
    """Create strip.png assets from the card artwork top section."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Take top portion of card at strip aspect ratio (375:144 ≈ 2.604:1)
    strip_h = min(card.height, round(card.width / (375 / 144)))
    strip_src = card.crop((0, 0, card.width, strip_h))
    for name, size in [
        ("strip.png", (375, 144)),
        ("strip@2x.png", (750, 288)),
        ("strip@3x.png", (1125, 432)),
    ]:
        cover_resize(strip_src, size).save(out_dir / name, "PNG")


def make_icon_images(out_dir: Path):
    """Gold-branded icon."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, size in [
        ("icon.png", (29, 29)),
        ("icon@2x.png", (58, 58)),
        ("icon@3x.png", (87, 87)),
    ]:
        icon = Image.new("RGBA", size, (188, 142, 59, 255))
        icon.save(out_dir / name, "PNG")


# ── build ──────────────────────────────────────────────────────────────

def build_pass_json(card_key: str, info: dict) -> dict:
    back_fields = []
    if info["body"]:
        back_fields.append({"key": "content", "label": "النص", "value": info["body"]})
    back_fields.append({
        "key": "snapchat",
        "label": "سناب شات",
        "value": "https://snapchat.com/t/njUz51fx",
        "attributedValue": '<a href="https://snapchat.com/t/njUz51fx">https://snapchat.com/t/njUz51fx</a>',
    })
    return {
        "formatVersion": 1,
        "passTypeIdentifier": "pass.sa.sakina.wallet",
        "serialNumber": f"sakina-{card_key}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "teamIdentifier": "KQHF5M39G9",
        "organizationName": "سكينة",
        "description": info["title"],
        "logoText": "سكينة",
        "foregroundColor": "rgb(255, 255, 255)",
        "backgroundColor": "rgb(18, 85, 130)",
        "labelColor": "rgb(220, 220, 220)",
        "storeCard": {
            "headerFields": [{"key": "type", "label": "", "value": info["title"]}],
            "secondaryFields": [
                {"key": "details", "label": "النص الكامل", "value": "اضغط ⓘ للذكر كاملاً"}
            ],
            "backFields": back_fields,
        },
    }


def rebuild_pass(card_key: str, info: dict, design_path: Path, out_path: Path):
    with tempfile.TemporaryDirectory(prefix=f"pkpass_{card_key}_") as tmp:
        pass_dir = Path(tmp)

        # Extract card artwork from mockup
        card = extract_wallet_card(design_path)

        # Create strip assets (NO background.png — it confuses storeCard)
        make_strip_images(card, pass_dir)

        # Create branded icon
        make_icon_images(pass_dir)

        # pass.json
        pass_json = build_pass_json(card_key, info)
        (pass_dir / "pass.json").write_text(
            json.dumps(pass_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # manifest + sign
        manifest_bytes = write_manifest(pass_dir)
        private_key, cert, extra_certs = load_p12(P12, P12_PASSWORD)
        signature = sign_manifest(manifest_bytes, private_key, cert, extra_certs)
        (pass_dir / "signature").write_bytes(signature)

        # zip
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            out_path.unlink()
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(pass_dir.iterdir()):
                if f.is_file():
                    zf.write(f, f.name)

    print(f"  ✅ {out_path.name}")


def main():
    if not PREVIEWS.exists():
        print(f"❌ Preview folder not found: {PREVIEWS}")
        sys.exit(1)
    if not P12.exists():
        print(f"❌ P12 not found: {P12}")
        sys.exit(1)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    print(f"🔨 Rebuilding ALL 8 passes → {OUTPUT}")
    print(f"   Style: storeCard | strip.png only (no background.png)")
    print(f"   Signing: {P12.name}\n")

    for design_path in sorted(PREVIEWS.glob("*.png")):
        card_key = design_path.stem
        info = CARDS.get(card_key)
        if not info:
            print(f"  ⚠️  Skipping {design_path.name} — no card data")
            continue
        out_path = OUTPUT / f"{card_key}.pkpass"
        rebuild_pass(card_key, info, design_path, out_path)

    print(f"\n🎉 DONE! {len(list(OUTPUT.glob('*.pkpass')))} passes in {OUTPUT}")
    print("   Send individual .pkpass files to client by email.")
    print("   ⚠️  Client MUST delete old passes from Wallet before installing new ones!")


if __name__ == "__main__":
    main()