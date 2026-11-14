"""Kamu ilan takibi: acik RSS kaynaklarini tarar, uygun ilanlari ntfy ile bildirir.

Kullanim:
  python takip.py            # yeni uygun ilanlari bildirir (NTFY_TOPIC yoksa sadece yazdirir)
  python takip.py --dry-run  # bildirim gondermez, seen.json'a yazmaz
Ilk calismada (seen.json yoksa) eski ilanlar sessizce 'gorulmus' sayilir.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = "ilan-takip-kisisel/1.0 (kisisel kullanim)"
SEEN = Path(__file__).with_name("seen.json")
MAX_BILDIRIM = 8

# Acik RSS kaynaklari. Google News sorgulari hedefli arama icin.
def gnews(q):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:3d")
            + "&hl=tr&gl=TR&ceid=TR:tr")

KAYNAKLAR = [
    "https://www.isinolsa.com/feed/",
    "https://www.kamu1.net/feed/",
    gnews("İzmir personel alımı ilanı"),
    gnews("KPSS şartsız personel alımı"),
    gnews("peyzaj mimarı alımı"),
    gnews("antrenör alımı sözleşmeli"),
    gnews("Ziraat Halkbank VakıfBank personel alımı"),
    gnews("astsubay uzman erbaş alımı"),
]

ISE_ALIM = ["alım", "alacak", "alınacak", "alıyor", "ilan", "başvuru", "başvurular"]
UYGUN = [
    "izmir", "kpss'siz", "kpsssiz", "kpss şartsız", "kpss şartı yok", "kpss aranmaz",
    "kpss'siz", "peyzaj", "antrenör", "spor eğitmeni", "ziraat bankası", "halkbank",
    "vakıfbank", "merkez bankası", "astsubay", "uzman erbaş", "sahil güvenlik", "jandarma",
]
HARIC = [
    "hemşire", "hekim", "doktor", "ebe ", "diyetisyen", "öğretim üyesi", "öğretmen",
    "sonuçları", "sonuçlar", "sonuç", "kura sonuç", "maaş", "zam", "yurt personeli",
    "temizlik", "güvenlik görevlisi", "sağlık personeli", "fiyat", "maç", "spor deplasman",
    "hastane", "nato", "açık iş", "bin açık",
]


def tr_lower(s):
    return s.replace("İ", "i").replace("I", "ı").lower()


def indir(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def oku(url):
    try:
        root = ET.fromstring(indir(url))
    except Exception as e:  # tek kaynak bozulursa digerleri calissin
        print(f"UYARI: {url[:60]} okunamadi: {e}", file=sys.stderr)
        return []
    out = []
    for it in root.iter("item"):
        baslik = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        ozet = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        if baslik and link:
            out.append({"baslik": baslik, "link": link, "ozet": ozet})
    return out


def uygun_mu(it):
    t = tr_lower(it["baslik"] + " " + it["ozet"][:300])
    bt = tr_lower(it["baslik"])
    if not any(k in t for k in ISE_ALIM):
        return False
    if any(k in bt for k in HARIC):  # haric kelimeler sadece baslikta aranir
        return False
    return any(k in t for k in UYGUN)


def bildir(topic, it):
    govde = {"topic": topic, "title": "Yeni ilan", "message": it["baslik"],
             "click": it["link"], "tags": ["briefcase"]}
    req = urllib.request.Request(
        "https://ntfy.sh/",
        data=json.dumps(govde).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30).read()


def main():
    dry = "--dry-run" in sys.argv
    ilk_calisma = not SEEN.exists()
    seen = set(json.loads(SEEN.read_text(encoding="utf-8"))) if not ilk_calisma else set()

    tum, gorulen = [], set()
    for url in KAYNAKLAR:
        for it in oku(url):
            if it["link"] in gorulen:
                continue
            gorulen.add(it["link"])
            tum.append(it)

    yeni = [it for it in tum if it["link"] not in seen and uygun_mu(it)]
    topic = os.environ.get("NTFY_TOPIC", "").strip()

    if ilk_calisma and not dry:
        print(f"Ilk calisma: {len(tum)} ilan sessizce gorulmus sayildi.")
        yeni = []
    else:
        for it in yeni[:MAX_BILDIRIM]:
            print("UYGUN:", it["baslik"], "|", it["link"])
            if topic and not dry:
                bildir(topic, it)
        if not topic and yeni:
            print("(NTFY_TOPIC tanimli degil, bildirim gonderilmedi)")

    if not dry:
        SEEN.write_text(
            json.dumps(sorted(seen | {it["link"] for it in tum}), ensure_ascii=False, indent=0),
            encoding="utf-8",
        )
    print(f"Taranan: {len(tum)}, yeni uygun: {len(yeni)}")


if __name__ == "__main__":
    main()
