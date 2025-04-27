# AI Web Sitesi Oluşturucu

AI Web Sitesi Oluşturucu, birkaç basit metin komutuyla Netlify üzerinde otomatik, modern ve duyarlı bir web sitesi inşa edebilen açık kaynak bir Python uygulamasıdır. Kullanıcı dostu ön yüzü (Streamlit) sayesinde teknik bilgi gerektirmeden, yapay zekâ destekli web sitesi oluşturma sürecini birkaç tıklamaya indirger.



---

## Özellikler

- **Doğal Dil ile Web Sitesi Tasarımı:** "Restoran sitesi oluştur" gibi komutlarla sıfırdan site üretimi
- **Yapay Zeka ile HTML/CSS/JS Kodları:** GGUF formatında modern dil modeliyle otomatik kod üretimi
- **Anında Önizleme:** Oluşturulan siteyi browserda canlı görüntüleme
- **Otomatik Netlify Yükleme:** Sitenizi anında Netlify'a deploy edin
- **Kayıt ve Revizyon:** Tüm komut geçmişi kayıt altında, revizyonlar anında uygulanabilir
- **Özel Domain & HTTPS:** Dilerseniz kendi domaininizi ekleyip SSL kurabilirsiniz

---


## Hızlı Başlangıç

### Gereksinimler

- Python 3.8 veya üzeri
- Git
- Netlify hesabı & API tokenı (Netlify için [token oluştur](https://app.netlify.com/user/applications/personal))

### 1. Repoyu Klonlayın

```bash
git clone https://github.com/oyelmali/ai-web-generator.git
cd ai-web-generator
```

### 2. Bağımlılıkları Kurun

```bash
cd backend
pip install -r requirements.txt
cd ../frontend
pip install -r requirements.txt
cd ..
```
### 3. AI Modelini İndirin

```bash
python download-model.py
```

## Çalıştırma

### Backend (API Sunucusu):

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```
### Frontend (Kullanıcı Arayüzü):
#### Farklı bir terminal penceresinde:

```bash
cd frontend
streamlit run app.py
```


## Kullanım

Site Adı Girin: Site adınızı oluşturun veya listeden kaydınızı seçin.
Komutunuzu Girin: "Modern portfolyo sitesi oluştur, renkler mavi olsun" tarzı istediğinizi yazın.
Oluştur/Güncelle: Butona tıklayın, AI modeli HTML kodunu üretsin ve sitenizi Netlify’a deploy etsin.
Önizleme ve Onay: Sitenizi görüntüleyebilir, yeni komutlarla tekrar güncelleyebilirsiniz.
Domain ve SSL: Yayım aşamasında size domain ve SSL seçenekleri sunulur.





