# PDF to Markdown

PDF dosyalarını yerel olarak Markdown'a çeviren kişisel bir araç. Docling
kullanır: sayfa düzenini, tabloları ve taranmış metni yapay zeka modelleriyle
çözer. Dosyalar hiçbir yere yüklenmez, her şey bu bilgisayarda çalışır.

Aracın kendisi (konsol mesajları, `--help`, kalite raporu) İngilizce konuşur.
Bu doküman Türkçe; İngilizcesi için [README.en.md](README.en.md).

## Kurulum

Windows'ta Python 3.10+ kurulu olmalı (python.org'dan indirirken "Add
python.exe to PATH" kutusunu işaretle). Sonra `install.bat` dosyasını bir kez
çalıştır: sanal ortamı kurar, Docling'i indirir ve Windows'un "Gönder" menüsüne
`pdftomd` kısayolunu ekler. İlk seferde birkaç dakika sürebilir. İlk dönüşümde
Docling kendi modellerini de indirir, o yüzden kurulum ve ilk çalıştırma internet
ister; sonrası tamamen çevrimdışı. `install.bat` yeniden çalıştırılırsa mevcut
sanal ortam ve paketler korunur; her şey sıfırdan tekrar kurulmaz.

## Kullanım

**Sürükle-bırak:** PDF'leri (bir veya birden fazla) `pdftomd.bat` dosyasının
üzerine bırak. Bir konsol penceresi açılır, ilerlemeyi yazar, bitince çıktı
klasörü Explorer'da açılır. Hata olursa pencere kapanmaz, mesajı okuyabilirsin.

**İstediğin dosyaları seç:** `install.bat`, Windows'un "Gönder" menüsüne
`pdftomd` kısayolunu ekler. Explorer'da istediğin sayıda PDF seç, sağ tıkla ve
Gönder → pdftomd yolunu kullan. Windows 11'de "Gönder", "Daha fazla seçenek
göster" altında olabilir. Klasörde dört PDF varken yalnızca ikisini seçersen
sadece o iki dosya dönüştürülür. Aracı bu kısayol eklenmeden önce kurduysan
`install.bat` dosyasını yeniden çalıştırabilirsin; kurulu paketler tekrar
kullanılır.

**Komut satırı:**

```powershell
.\pdftomd.bat                                             # bu klasördeki bütün PDF'ler
.\pdftomd.bat --yes                                       # aynı işlem, onay sormadan
.\pdftomd.bat "C:\Belgeler\ornek.pdf"                     # tek dosya
.\pdftomd.bat --fast "C:\Belgeler\ornek.pdf"              # hızlı profil
.\pdftomd.bat "C:\Belgeler\a.pdf" "C:\Belgeler\b.pdf"     # birden fazla
.\pdftomd.bat "C:\Belgeler\ornek.pdf" -o "C:\cikti"       # çıktı klasörü
.\pdftomd.bat --no-open "C:\Belgeler\ornek.pdf"           # Explorer penceresi açmaz
.\pdftomd.bat --no-report "C:\Belgeler\ornek.pdf"         # kalite raporu yazmaz
.\pdftomd.bat --help                                      # tüm seçenekler
```

**Geçerli klasör:** Hiç PDF yolu verilmezse araç, çalıştırıldığı klasörün
doğrudan içindeki bütün `.pdf` dosyalarını bulur. Büyük-küçük harf ayrımı yapmaz
ve alt klasörleri taramaz. Örneğin batch dosyası nerede kurulu olursa olsun
`C:\Belgeler` içindeki PDF'leri dönüştürmek için:

```powershell
cd "C:\Belgeler"
C:\araclar\pdftomd\pdftomd.bat
```

Önce klasör ve dosya adları gösterilir. Etkileşimli bir konsolda birden fazla
PDF bulunursa başlamak için `yes` yaz; başka her cevap işlemi iptal eder. Bu
soruyu atlamak için `--yes` kullan. Betiklerde ve diğer etkileşimsiz
çalıştırmalarda soru sorulmadan devam edilir.

## Çıktı

Tek PDF'de çıktı, PDF'in yanına oluşturulur:

```text
ornek_markdown/
├── ornek.md          okunacak dosya
├── ornek.json        Docling'in yapısal kaydı
├── ornek_report.md   dönüşümde ne kaybolduğunun raporu
└── ornek_artifacts/  belgeden çıkarılan görseller (PNG)
```

Görseller Markdown'ın **içine gömülmez**, ayrı dosya olarak durur ve `.md`
onlara bağlantı verir. Markdown dosyasını başka bir yere taşırsan `_artifacts`
klasörünü de yanında taşı, yoksa resimler görünmez.

`.json` dosyası Markdown'a sığmayan bilgileri saklar: her bloğun hangi sayfada
ve sayfanın neresinde olduğu, tabloların hücre hücre yapısı (birleşik hücreler
dahil), blok tipleri. Arama/RAG sistemine besleme veya "bu cümle kaçıncı
sayfada" sorusunu cevaplama gibi işler için. Sadece okuyacaksan silebilirsin,
Markdown ondan bağımsız çalışır.

Birden fazla PDF verildiğinde `-o` yoksa ilk PDF'in yanında ortak bir klasör
açılır; aynı isimli dosyalar `_2`, `_3` ekiyle ayrılır:

```text
pdfmd_output/
├── bir_markdown/
└── iki_markdown/
```

`-o` verilirse tek PDF'de doğrudan hedef klasör, çoklu PDF'de belge
klasörlerinin altına açılacağı ortak kök olur. Bir dosya hata alırsa diğerleri
işlenmeye devam eder, sonunda özet yazılır.

## Kalite raporu

Her dönüşümün sonunda araç kısa bir Quality Report v2 özeti yazar. Aşağıdaki
sayılar yalnızca örnektir; yeniden üretilmiş bir belge ölçümü değildir:

```text
Quality Report v2 | Extraction: transfer 98.0% (980/1000); unexplained 10; order risks 2 | Serialization: transfer 99.0% (990/1000); unexpected 5; order risks 1
Structure: PASS | headings 12/12; lists 3/3 (items 18/18); tables 4/4 (cells 86/86); links 2/2; images 5/5; stale 0
```

Ayrıntısı `<ad>_report.md` dosyasına yazılır. Çıkarım (PDF metin katmanından
DoclingDocument'a) ile serileştirme (DoclingDocument'tan görünür Markdown'a)
ayrı token sayıları, oranlar, muhasebe eşitlikleri ve oluşum tabanlı sorun
örnekleri taşır. Bu, metin katmanı uyum kanıtıdır; doğrulanmış belge doğruluğu
değildir. Yapısal bölüm ayrıca DoclingDocument ile Markdown arasındaki başlık,
liste, tablo hücresi ve bağlantı oluşumlarını karşılaştırır. Yerel hedeflerin
çıktı klasörü içinde kaldığını denetler; görselleri gerçekten açıp biçim ve
boyutlarını kaydeder, eksik/boş/geçersiz veya stale artifact'ları gösterir.
Dış bağlantıları ağdan açmaz. Bu kontroller serileştirme bütünlüğüdür; Docling'in
kaynak PDF'yi doğru çıkardığını tek başına kanıtlamaz.

En çok işe yaradığı yer taranmış belgeler. Metin katmanı olmayan bir PDF'i
`--fast` ile çevirirsen çıktı sessizce boş kalır; rapor bunu söyler:

```text
Quality Report v2 | Extraction: transfer n/a (no source tokens); unexplained 0; order risks 0 | Serialization: transfer n/a (no source tokens); unexpected 0; order risks 0
Structure: PASS | headings 0/0; lists 0/0 (items 0/0); tables 0/0 (cells 0/0); links 0/0; images 0/0; stale 0
WARNING: 2 pages without a text layer are unverified; --fast turned OCR off, so they may have come out empty. Coverage cannot be measured. Try again with --quality.
```

Rapor istemezsen `--no-report` ver.

Sayaç artık her uzunluktaki Unicode harf ve sayıyı kapsar; `A`, `ve`, `7` ve
`42` gibi kısa sözcükler ve tablo değerleri sessizce atılmaz. Unicode uyumluluk
normalizasyonu `ﬁ` gibi ligatürleri düz harflerle eşleştirir.

Büyük-küçük harf işleminin açık bir belge profili vardır. Varsayılan `unicode`
profili dilden bağımsız Unicode harf katlaması uygular; İngilizce `RISK`/`risk`,
`TITLE`/`title` ve `I`/`i` eşleşir. Token modeli, açıkça seçilen bir `turkic`
profilini de destekler; bu profilde `İ`/`i` ile `I`/`ı` ayrı çiftlerdir. Araç
belgenin dilini tahmin etmez: tek bir dilden bağımsız metin biçimi `I` harfinin
iki yorumunu da güvenle karşılayamaz.

`risk-based` gibi aynı satırdaki gerçek bileşik tireyi korur. Satır sonundaki
tire ise sözcük bölünmesi de, satıra sığmayan gerçek bir bileşik de olabilir.
Token her ham ayırıcı aralığını, tireyi koruyan temkinli biçimi ve her ayırıcı
için bağımsız koru/birleştir seçeneğini saklar. Sıralı hizalama yalnızca komşu
token'lar desteklediğinde birleştirir ve bu kararı normal eşleşmeden ayrı tutar.

Analiz yolu artık oluşum tabanlı iki ayrı sonuç kurar: PDF metin katmanından
DoclingDocument'a (çıkarım), ardından DoclingDocument'tan görünür Markdown'a
(serileştirme). Hizalama sayfa bölümlüdür ve 64 token'lık sınırlı bir LCS
penceresi kullanır; kaynak/provenans kanıtını korur, olası okuma sırası
taşımalarını risk olarak gösterir ve tek oluşumu yeniden kullanmaz. Birden çok
Docling provenans girdisi token `charspan` değerleriyle eşlenir; belirsiz sayfa
bilgisi tahmin edilmez. Şekil ve üstbilgi/altbilgi açıklamaları yalnızca PDF
karakter kutuları Docling bölgesiyle örtüşüyorsa kabul edilir. Görünür URL ve
e-posta otomatik bağlantıları tokenlaştırılırken gerçek HTML etiketleri sözdizimi
olarak maskelenir. V2; kabul edilen aktarımı, açıklanan kaybı, açıklanamayan
kaybı, beklenmeyen eklemeleri, ikameleri ve sıra risklerini aktarım oranına
karıştırmadan gösterir. Sıfır payda `n/a` olarak yazılır. Eski sözcük torbası
yüzdesi yalnızca `legacy_coverage` tanı geçmişi olarak kalır. İşlem ve metrik
sözleşmesi, sınırlar ve sentetik ölçümler
[`docs/ALIGNMENT.md`](docs/ALIGNMENT.md) içinde açıklanır.

## Hangi profil?

| | `--fast` | varsayılan (`--quality`) |
|---|---|---|
| Hız (5 sayfa) | 13 sn | 30 sn |
| Metin ve görseller | aynı | aynı |
| Tablolar | satır/sütun kaybolur, hücreler tek satıra yığılır | gerçek satır ve sütunlar |
| Taranmış sayfa | boş çıkar | OCR ile metin çıkar |

Fark tam olarak iki ayar: `--fast`, OCR ve tablo yapısı modellerini kapatır.

**Kural:** taranmış belge veya tablo varsa varsayılanda bırak; düz metin
(roman, makale, sözleşme) ise `--fast` kullan. Emin değilsen varsayılan
seçenek hiçbir şey kaybettirmez, sadece yavaştır. Son sıcak-cache doğrulamasında
95 sayfalık tablo ağırlıklı NIST belgesi varsayılan profilde 276 saniyede
dönüştü; model yükleme ve CLI kapanışı dahil uçtan uca süre 283,355 saniyeydi.

`--formula` matematik formüllerini LaTeX'e çevirir. İlk kullanımda 631 MB'lık
ek bir model iner; indirme yarıda kesilirse sonraki çalıştırmada kaldığı yerden
devam eder. Fast veya quality ile birlikte kullanılabilir.

## Ne korunur, ne kaybolur

95 sayfalık NIST SP 800-30 belgesi 8 Eylül 2026'da önbellekteki modellerle,
offline ve varsayılan `--quality` profilinde Quality Report v2 ile yeniden
ölçüldü:

- Çıkarım aktarımı: **%93,44** (39.921/42.724); açıklanmış kayıp %2,73,
  açıklanamayan kayıp %0,64 ve 1.364 okuma sırası riski.
- Serileştirme aktarımı: **%98,37** (40.680/41.355); açıklanamayan kayıp %0,11,
  beklenmeyen ekleme %0,23 ve 436 okuma sırası riski.
- Yapısal bütünlük: **PASS** — 152 başlık, 40 liste/183 item, 55 tablo/1.274
  hücre ve 7/7 geçerli PNG; eksik veya stale artifact yok.
- Son sıcak-cache doğrulamasında uçtan uca süre 283,355 saniyeydi. İlk iki
  offline ölçüm koşusundaki geçerli süreç örneklerinde gözlenen en yüksek
  `PeakWorkingSet64` 3.587.977.216 bayt (3,342 GiB) oldu.

Eski Quality Report v1 ile ölçülen **%99,6** yalnız tarihsel bir kapsama
tanısıdır. Üç karakterden kısa sözcükleri atlayan ve oluşumları bire bir
saymayan eski sayaçla üretildi; v2 aktarım oranlarıyla doğrudan karşılaştırılamaz.
Bu değerlerin hiçbiri elle doğrulanmış ground truth olmadığı için belge
doğruluğu yüzdesi değildir.

Korunan: başlık düzeyleri, paragraf ve liste yapısı, tablo verisi, görsellerin
metin içindeki konumu, dipnotlar. Sayfa üstbilgi/altbilgileri kasten atılır.

Kaybolan:

- **İtalik ve kalın vurgular** düz metne dönüşür.
- **Birleşik tablo hücreleri** Markdown'da olmadığı için değer tekrarlanır:
  üç sütuna yayılan bir başlık `| Provided To | Provided To | Provided To |`
  şeklinde çıkar. Gerçek yapı `.json` içinde `colspan` olarak durur.
- **Süslü baş harfler** (bölüm başlarındaki büyük harf) düşer: `This` → `his`.
- **Üst simge dipnot numaraları** düz metne iner.
- **Şekillerin içine çizilmiş yazılar** metin olarak çıkmaz, resmin içinde
  kalır.

## Proje yapısı

```text
src/pdftomd/
├── __main__.py        `python -m pdftomd` girişi
├── cli.py             argümanlar, ilerleme mesajları, çıkış kodları
├── converter.py       Docling ile dönüşüm ve çıktı yolları
├── quality_report.py  kanıt toplama ve Quality Report v2 üretimi
├── quality_metrics.py aşama başına v2 sayaçları, oranları ve muhasebe eşitlikleri
└── alignment.py       sınırlı iki aşamalı oluşum hizalaması
tests/                 her modül için ayrı test dosyası
tests/fixtures/        PDF regresyon corpus'u ve makinece denetlenen gerçekler
docs/                  notlar ve yapılacaklar (İngilizce)
```

`pdftomd.bat`, `src` klasörünü içe aktarma yoluna ekleyip `python -m pdftomd`
çağırır; ayrıca kurulum gerektirmez.

## Testler

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

Bu hızlı komut canlı Docling corpus testini atlar. Modeller ilk kurulumda önbelleğe
alındıktan sonra tamamen çevrimdışı entegrasyon çalıştırma adımları
[`tests/fixtures/README.md`](tests/fixtures/README.md) içinde.
