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

Her dönüşümün sonunda araç, PDF'in metin katmanını ürettiği Markdown ile
karşılaştırır ve tek satırlık bir özet yazar:

```text
Quality: 99.6% word coverage | 55 tables, 7 images
```

Ayrıntısı `<ad>_report.md` dosyasına yazılır: kaç kelimenin geçtiği, geçmeyenlerin
nerede kaldığı (şeklin içinde, sayfa üstbilgisinde, dipnot numarasına yapışık),
açıklanamayan kaybın en çok olduğu sayfalar ve o belgede Markdown'ın taşıyamadığı
şeyler.

En çok işe yaradığı yer taranmış belgeler. Metin katmanı olmayan bir PDF'i
`--fast` ile çevirirsen çıktı sessizce boş kalır; rapor bunu söyler:

```text
Quality: the PDF has no text layer (scanned document), coverage cannot be measured
WARNING: 2 pages have no text layer and --fast turned OCR off; those pages may
have come out empty. Try again with --quality.
```

Rapor istemezsen `--no-report` ver.

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
seçenek hiçbir şey kaybettirmez, sadece yavaştır. Ölçüm: 95 sayfalık tablo
ağırlıklı bir belge varsayılan profilde ~5 dakika sürdü.

`--formula` matematik formüllerini LaTeX'e çevirir. İlk kullanımda 631 MB'lık
ek bir model iner; indirme yarıda kesilirse sonraki çalıştırmada kaldığı yerden
devam eder. Fast veya quality ile birlikte kullanılabilir.

## Ne korunur, ne kaybolur

95 sayfalık bir NIST dokümanıyla ölçüldü: PDF'in metin katmanındaki kelimelerin
**%99,6'sı** Markdown'da yerini aldı.

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
└── quality_report.py  PDF ile Markdown'ı karşılaştıran kalite ölçümü
tests/                 her modül için ayrı test dosyası
docs/                  notlar ve yapılacaklar (İngilizce)
```

`pdftomd.bat`, `src` klasörünü içe aktarma yoluna ekleyip `python -m pdftomd`
çağırır; ayrıca kurulum gerektirmez.

## Testler

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```
