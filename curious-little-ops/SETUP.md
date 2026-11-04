# Curious Little Ops - kurulum (bir kez, yaklaşık 1 saat toplam)

Sistem şöyle çalışır:

- **Google Drive / `curious-little-ops/`** klasörü: `state.json` (işin beyni: ürünler, KPI, içerik kuyruğu, kararlar), `secrets.json` (API anahtarları), `reports/` (KDP raporları).
- **Bu repo** (`curious-little-ops/`): kod + `assets/` (pin ve post görselleri, herkese açık URL ile servis edilir).
- **Zamanlanmış Claude görevleri:** "CL - Haftalık CEO" (Pazartesi) ve "CL - Günlük yayın" (her gün). Her çalışma bu repoyu klonlar, Drive'dan `state.json` + `secrets.json` indirir, scriptleri çalıştırır, `state.json`'ı Drive'a geri yazar.
- **Onay akışı:** Para kararları (fiyat, reklam bütçesi, listing gizleme) size e-posta ile gelir. Cevap olarak `approve D-xxxxxx` veya `reject D-xxxxxx` yazarsınız. Pin/post/Reel/Short onaysız yayınlanır.

API anahtarları olmadan da sistem çalışır: haftalık CEO özeti gelir, kuyruğa içerik eklenir, ama yayın yapılamaz ve KPI'lar elle girilir. Aşağıdaki adımlar tamamlandıkça ilgili kanal otomatikleşir.

## 0. Laptop hazırlığı

```
git clone https://github.com/nic42991/claude-scheduler
cd claude-scheduler/curious-little-ops
pip install -r requirements.txt
```

Drive'daki `secrets.json` şablonunu indirip bu klasöre koyun. Her adımda bu dosyaya değer yazacaksınız; bitince Drive'a geri yükleyin (aynı isimle üzerine yazın).

## 1. Pinterest (15 dk) - en önemli kanal, önce bunu yapın

1. https://developers.pinterest.com/apps/ -> **Create app**. İsim: Curious Little Ops. Trial access yeterli (kendi hesabınıza pin atabilir).
2. App ayarlarında **Redirect URI**: `http://localhost:8767/callback`
3. App ID ve App secret'ı alın. Laptop'ta:
   ```
   python3 scripts/pinterest_auth.py <APP_ID> <APP_SECRET>
   ```
   Tarayıcı açılır, onaylayın. Script board listesini ve token'ı yazar.
4. `secrets.json`: `pinterest_token`, `pinterest_board_id` (pinlerin gideceği board; genelde "Kids Printables" gibi ana board).
5. Token 30 gün geçerli. Script'in yazdığı refresh_token'ı saklayın; süresi dolunca aynı script tekrar çalıştırılır (haftalık özet "pinterest: 401" derse zamanı gelmiştir).

## 2. Instagram (20 dk)

1. Instagram hesabı **Business** olmalı ve bir **Facebook Sayfası**na bağlı olmalı (Instagram ayarları -> Hesap türü -> Business; sonra Sayfa bağla. Sayfa yoksa facebook.com/pages/create ile "Curious Little by Gozde" sayfası açın).
2. https://developers.facebook.com/apps -> Create app -> tip **Business** -> ürün olarak **Instagram Graph API** ekleyin.
3. Tools -> **Graph API Explorer**: uygulamanızı seçin, izinler: `instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, business_management`. **Generate Access Token** (kısa ömürlü user token).
4. Uzun ömürlü token'a çevirin (tarayıcıda açın, değerleri doldurun):
   ```
   https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=KISA_TOKEN
   ```
5. Sayfa token'ı ve IG user id:
   ```
   https://graph.facebook.com/v21.0/me/accounts?access_token=UZUN_TOKEN
   ```
   -> sayfanızın `id` ve `access_token`'ı (bu sayfa token'ı süresiz).
   ```
   https://graph.facebook.com/v21.0/SAYFA_ID?fields=instagram_business_account&access_token=SAYFA_TOKEN
   ```
   -> `instagram_business_account.id`
6. `secrets.json`: `instagram_token` = sayfa token, `instagram_user_id` = o id.
7. Uygulama "Development" modunda kalabilir; kendi hesabınıza yayın için App Review gerekmez.

## 3. YouTube (15 dk)

1. https://console.cloud.google.com -> yeni proje "curious-little-ops" -> **APIs & Services -> Enable** -> "YouTube Data API v3".
2. **OAuth consent screen**: External, uygulama adı, test users'a kanalın Google hesabını ekleyin.
3. **Credentials -> Create -> OAuth client ID -> Desktop app**. Client ID + secret.
4. Laptop'ta (kanal sahibi Google hesabı ile giriş yapın):
   ```
   python3 scripts/youtube_auth.py <CLIENT_ID> <CLIENT_SECRET>
   ```
5. `secrets.json`: `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token`.
6. Günlük kota 10.000 birim, bir yükleme ~1.600: günde en fazla 6 Short. Fazlası gerekmez.

## 4. Etsy (başvuru 1-5 gün, sonra 10 dk)

1. https://www.etsy.com/developers/your-apps -> **Create a New App**. Açıklama: "Internal tool to read my shop's orders and reviews and manage my own listings." Kişisel kullanım seçin. Onay e-postası gelince devam.
2. App'te **Callback URL**: `http://localhost:8765/callback`
3. Laptop'ta:
   ```
   python3 scripts/etsy_auth.py <KEYSTRING>
   ```
4. `secrets.json`: `etsy_keystring`, `etsy_shared_secret`, `etsy_refresh_token`, `etsy_shop_id`.
5. Etsy refresh token her kullanımda yenilenir; haftalık özet "etsy: refresh token rotated - update secrets.json" derse yeni değeri `secrets.json`'a yazın (görev bunu otomatik yapmaya çalışır, mesaj gelirse elle yapın).

Etsy API sipariş, yorum, listing fiyat/durum verir ama **ziyaret ve dönüşüm istatistiklerini vermez**. O rakamlar iki yolla gelir: (a) Pazartesi sabahı Shop Manager -> Stats ekran görüntüsünü haftalık özet e-postasına cevap olarak atarsınız, (b) laptop açık ve Chrome eklentisi bağlıysa görev kendisi okur.

## 5. Amazon KDP ve Amazon Ads

KDP'nin API'si yok. Ayda bir (ya da haftalık özet istediğinde) https://kdpreports.amazon.com -> Reports -> **Orders** raporunu xlsx indirip Drive'daki `curious-little-ops/reports/` klasörüne atın. Dosya adı önemsiz; görev en yeni dosyayı okur.

Amazon Ads için: https://advertising.amazon.com -> kampanya -> **Search term report** indirip aynı klasöre atın. Harcama/satış rakamlarını da özet e-postasına cevap olarak yazabilirsiniz: `ads_spend=35 ads_sales=20`.

## 6. Görselleri sisteme vermek

Pin ve post görselleri `assets/` klasöründen herkese açık servis edilir. İki yol:

- Görev kendisi üretir: ürün listing fotoğrafı + başlıktan marka kartı (`scripts/enqueue.py --make-image`).
- Siz Canva'dan export edip `assets/` içine commit edersiniz (GitHub web arayüzünden "Add file -> Upload files" yeterli).

Ürün listing fotoğraflarını bir kez `assets/products/<product_id>.jpg` olarak yükleyin (örn. `assets/products/P-xmas5in1.jpg`); görev bunlardan sınırsız pin kartı üretir.

## 7. Kontrol

```
python3 scripts/check_setup.py
```
Her kanal için `"ok": true` görmelisiniz. Sonra `secrets.json`'ı Drive'a yükleyin. Bir sonraki görev çalışmasında kanal otomatikleşir.

## Onay komutları (e-posta cevabı olarak)

- `approve D-1a2b3c` / `onayla D-1a2b3c`
- `reject D-1a2b3c` / `red D-1a2b3c`
- KPI girişi: `etsy_visits=2810 etsy_orders=3 ads_spend=35 ads_sales=41`
- Serbest talimat: "bu hafta Montessori pack'e ağırlık ver" gibi cümleler de okunur ve planlamaya yansır.
