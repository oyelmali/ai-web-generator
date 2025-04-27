import requests
import os
import hashlib

# Netlify API erişimi için kişisel erişim tokeni
# Bu token ile Netlify API'sine kimlik doğrulama yapılacak
NETLIFY_TOKEN = "nfp_VBrTjLcbiZaWiZu7SfxbhijxPYuh6PAx061c"  # kendi tokenını buraya koy!
DIR = "website"  # Deploy edilecek dosyaların bulunduğu klasör

# Tüm API isteklerinde kullanılacak ortak header'lar
headers = {
    "Authorization": f"Bearer {NETLIFY_TOKEN}",  # Bearer token kimlik doğrulama
    "Content-Type": "application/json"           # JSON formatında veri gönderimi
}

def find_existing_site(site_name):
    """
    Netlify hesabında verilen isimde bir site olup olmadığını kontrol eder
    
    Netlify API'sine istek göndererek tüm siteleri çeker ve
    verilen site_name ile eşleşen bir site varsa onun ID'sini döndürür.
    
    Args:
        site_name (str): Aranacak site adı
        
    Returns:
        str or None: Site bulunursa site ID'si, bulunamazsa None
    """
    url = f"https://api.netlify.com/api/v1/sites"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("Sitelist alınamadı:", resp.text)
        return None
    for site in resp.json():
        if site["name"] == site_name:
            return site["id"]
    return None

def create_site(site_name):
    """
    Verilen isimde yeni bir Netlify sitesi oluşturur
    
    Args:
        site_name (str): Oluşturulacak sitenin adı
        
    Returns:
        str or None: Başarılı olursa site ID'si, başarısız olursa None
    """
    url = "https://api.netlify.com/api/v1/sites"
    payload = {"name": site_name}  # Yeni site için gerekli minimum veri
    resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code in [200, 201]:
        data = resp.json()
        print(f"✅ Yeni site oluşturuldu: {data['name']} (id: {data['id']})")
        return data['id']
    elif resp.status_code == 422 and "already in use" in resp.text:
        # 422 hatası "unprocessable entity" - özellikle bu isimde bir site zaten varsa
        print("Bu alt alan başka bir Netlify kullanıcısına ait.")
    else:
        print("Beklenmeyen hata:", resp.status_code, resp.text)
    return None

def find_or_create_site(site_name):
    """
    Verilen isimde site varsa bulur, yoksa yeni oluşturur
    
    Bu fonksiyon önce find_existing_site ile siteyi arar,
    bulunamazsa create_site ile yeni bir site oluşturur.
    
    Args:
        site_name (str): Bulunacak veya oluşturulacak site adı
        
    Returns:
        str or None: Site ID'si, başarısız olursa None
    """
    site_id = find_existing_site(site_name)
    if site_id:
        print(f"🟢 {site_name} adlı site bulundu (ID: {site_id})")
        return site_id
    else:
        print(f"🔵 {site_name} adlı site bulunamadı, yeni site açılıyor...")
        return create_site(site_name)

def sha1sum(filename):
    """
    Verilen dosyanın SHA1 hash değerini hesaplar
    
    Bu hash değeri, Netlify'ın dosyaları tanımlaması için kullanılır.
    Sadece değişen dosyaların yüklenmesini sağlayan akıllı deploy mekanizması için gereklidir.
    
    Args:
        filename (str): Hash'i hesaplanacak dosyanın yolu
        
    Returns:
        str: Dosyanın SHA1 hash değeri
    """
    h = hashlib.sha1()
    with open(filename, 'rb') as file:
        while True:
            chunk = file.read(8192)  # Dosyayı 8KB'lık parçalara bölerek işle
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def collect_files(root_dir):
    """
    Verilen dizindeki tüm dosyaları recursive olarak toplar
    
    Args:
        root_dir (str): Dosyaların bulunduğu kök dizin
        
    Returns:
        list: (göreceli_yol, tam_yol) çiftlerinden oluşan liste
    """
    files = []
    for root, _, filenames in os.walk(root_dir):
        for fname in filenames:
            path = os.path.join(root, fname)  # Dosyanın tam yolu
            relpath = os.path.relpath(path, root_dir)  # Kök dizine göre göreceli yolu
            files.append((relpath.replace("\\","/"), path))  # Windows/Unix uyumluluğu için \ → /
    return files

def deploy_to_site(site_id, html_code=None):
    """
    Dosyaları Netlify sitesine deploy eder
    
    Bu fonksiyon Netlify'ın iki aşamalı deploy mekanizmasını kullanır:
    1. Dosya listesi ve hash'lerini göndererek hangi dosyaların yüklenmesi gerektiğini öğrenir
    2. Sadece gereken dosyaları yükler
    
    Args:
        site_id (str): Netlify site ID'si
        html_code (str, optional): Eğer verilirse index.html olarak kaydedilir ve deploy edilir
        
    Returns:
        str or None: Deploy başarılıysa site URL'i, değilse None
    """
    # Eğer yeni html_code verilirse, kaydet
    if html_code:
        os.makedirs(DIR, exist_ok=True)  # Klasör yoksa oluştur
        with open(os.path.join(DIR, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_code)
    
    files = collect_files(DIR)  # Tüm dosyaları topla
    if not files:
        print(f"{DIR} klasöründe deploy edilecek dosya yok!")
        return None

    # 1. Deploy başlat: Hash listesi paylaşılır
    # Netlify'a dosya içeriklerini göndermeden önce hangi dosyaların değiştiğini belirlemek için
    # dosya yolları ve hash değerlerinden oluşan bir manifest gönderilir
    manifest = {rel: sha1sum(path) for rel, path in files}
    deploy_resp = requests.post(
        f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
        headers=headers,
        json={"files": manifest}
    )
    if deploy_resp.status_code not in [200, 201]:  # Düzeltildi: != yerine not in
        print(f"Deploy başlatılırken hata! Kod: {deploy_resp.status_code}")
        print(deploy_resp.text)
        return None

    deploy = deploy_resp.json()
    required = deploy.get("required", [])  # Netlify'ın istediği dosyaların hash'leri
    deploy_id = deploy.get("id")  # Deploy işleminin ID'si
    
    print(f"Deploy ID: {deploy_id}")
    print(f"Yüklenmesi gereken dosyalar: {required}")

    # 2. Eksik dosyaları upload et
    for relpath in required:
        abspath = None
        # Hash'e karşılık gelen dosya yolunu bul
        for file_rel, file_path in files:
            if sha1sum(file_path) == relpath:
                abspath = file_path
                relpath = file_rel
                break
        
        if not abspath:
            print(f"Hata: {relpath} hash'ine sahip dosya bulunamadı!")
            continue
            
        # Dosyayı API'ye gönder
        with open(abspath, "rb") as f:
            put_resp = requests.put(
                f"https://api.netlify.com/api/v1/deploys/{deploy_id}/files/{relpath}",
                headers={
                    "Authorization": f"Bearer {NETLIFY_TOKEN}",
                    "Content-Type": "application/octet-stream"  # Binary veri gönderimi
                },
                data=f
            )
            if put_resp.status_code == 200:
                print(f"Yüklendi: {relpath}")
            else:
                print(f"Hata: {relpath} -- Kod: {put_resp.status_code}", put_resp.text)

    print(f"✅ Deploy tamamlandı!")
    
    # Yayın linkini bul ve döndür
    site_info = requests.get(f"https://api.netlify.com/api/v1/sites/{site_id}", headers=headers)
    if site_info.status_code == 200:
        site_url = site_info.json()["url"]
        print(f"🌐 Site linki: {site_url}")
        return site_url
    return None


def finalize_site_setup(site_id):
    """
    Netlify sitesinin kurulum işlemlerini tamamlar
    
    Bu fonksiyon, kullanıcı site içeriğini onayladıktan sonra çalışır ve
    sitenin üretim ortamında optimum performans göstermesi için gerekli
    ayarlamaları yapar.
    
    Yapılan işlemler:
    - SSL sertifikası oluşturma
    - HTTPS yönlendirmesi
    - CSS/JS minification ve bundling
    - Görüntü optimizasyonu
    - Deploy'u üretim durumuna yükseltme
    
    Args:
        site_id (str): Netlify site ID'si
        
    Returns:
        str or None: İşlem başarılıysa site URL'si, değilse None
    """
    if not site_id:
        print("Hata: Site ID bulunamadı")
        return None
        
    try:
        # Site varlığını kontrol et - geçerli bir site ID'si mi?
        site_check = requests.get(
            f"https://api.netlify.com/api/v1/sites/{site_id}", 
            headers=headers
        )
        
        if site_check.status_code != 200:
            print(f"Hata: Site bulunamadı (ID: {site_id})")
            return None

        # 1. HTTPS ayarlarını yapılandır - güvenli bağlantı
        https_resp = requests.patch(
            f"https://api.netlify.com/api/v1/sites/{site_id}",
            headers=headers,
            json={
                "ssl": True,  # SSL sertifikası oluştur (Let's Encrypt)
                "force_ssl": True,  # HTTP isteklerini HTTPS'ye yönlendir
            }
        )
        
        if https_resp.status_code not in [200, 201, 204]:
            print(f"SSL yapılandırma hatası: {https_resp.status_code}")
            print(https_resp.text)
            return False
            
        print("✅ SSL yapılandırması tamamlandı")
        
        # 2. Site ayarlarını optimize et - daha iyi performans için
        optimize_resp = requests.patch(
            f"https://api.netlify.com/api/v1/sites/{site_id}",
            headers=headers,
            json={
                "processing_settings": {
                    "html": {
                        "pretty_urls": True,  # .html uzantılarını gizle (örn. /about.html → /about)
                    },
                    "css": {
                        "bundle": True,  # CSS dosyalarını tek dosya haline getir (daha az HTTP isteği)
                        "minify": True   # CSS dosyalarını küçült (boşlukları ve yorumları kaldır)
                    },
                    "js": {
                        "bundle": True,  # JS dosyalarını tek dosya haline getir
                        "minify": True   # JS dosyalarını küçült
                    },
                    "images": {
                        "optimize": True  # Görüntüleri sıkıştır ve optimize et
                    }
                }
            }
        )
        
        if optimize_resp.status_code not in [200, 201, 204]:
            print(f"Site optimizasyon hatası: {optimize_resp.status_code}")
            print(optimize_resp.text)
            return False
            
        print("✅ Site optimizasyonu tamamlandı")
        
        # 3. Site bilgilerini al (güncel URL ve deploy ID için)
        site_info = requests.get(
            f"https://api.netlify.com/api/v1/sites/{site_id}", 
            headers=headers
        )
        
        if site_info.status_code == 200:
            site_data = site_info.json()
            site_url = site_data["url"]
            site_name = site_data["name"]
            
            # 4. En son deploy'u "production" durumuna yükselt
            # Bu, deploy'un önbelleğe alınmasını ve CDN üzerinde dağıtılmasını sağlar
            deploy_resp = requests.post(
                f"https://api.netlify.com/api/v1/sites/{site_id}/deploys/{site_data['deploy_id']}/restore",
                headers=headers
            )
            
            if deploy_resp.status_code in [200, 201, 204]:
                print("✅ Deploy production'a yükseltildi")
            
            print(f"🌐 Site kurulumu tamamlandı: {site_url}")
            return site_url
        else:
            print(f"Site bilgileri alınamadı: {site_info.status_code}")
            return None
            
    except Exception as e:
        print(f"Site kurulum hatası: {str(e)}")
        return None
    

def add_custom_domain(site_id, domain):
    """
    Netlify sitesine özel domain ekler ve birincil domain olarak ayarlar
    
    Bu fonksiyon iki adımda çalışır:
    1. Verilen domain'i siteye ekler
    2. Eklenen domain'i birincil domain olarak ayarlar
    
    Not: Domainin DNS ayarlarının da doğru yapılandırılması gerekir.
    Netlify'ın önerdiği DNS ayarlarını domain sağlayıcınızda yapmanız gerekir.
    
    Args:
        site_id (str): Netlify site ID'si
        domain (str): Eklenecek özel domain (örn. "example.com")
        
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    try:
        # Domaini ekle
        domain_resp = requests.post(
            f"https://api.netlify.com/api/v1/sites/{site_id}/domains",
            headers=headers,
            json={"hostname": domain}  # Eklenecek domain adı
        )
        
        if domain_resp.status_code in [200, 201]:
            print(f"✅ Domain eklendi: {domain}")
            
            # Domain'i birincil domain olarak ayarla
            # Bu, Netlify'ın *.netlify.app domaini yerine bu özel domaini ana URL olarak kullanmasını sağlar
            primary_resp = requests.post(
                f"https://api.netlify.com/api/v1/sites/{site_id}/domain_aliases/{domain}/primary",
                headers=headers
            )
            
            if primary_resp.status_code in [200, 201, 204]:
                print(f"✅ {domain} birincil domain olarak ayarlandı")
                return True
            else:
                print(f"Birincil domain hatası: {primary_resp.status_code}")
                print(primary_resp.text)
        else:
            print(f"Domain ekleme hatası: {domain_resp.status_code}")
            print(domain_resp.text)
            return False
            
    except Exception as e:
        print(f"Özel domain ekleme hatası: {str(e)}")
        return False