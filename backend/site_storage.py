import json
import os
from datetime import datetime

# Depolama dosyası - sitelerin bilgilerinin saklanacağı JSON dosyası
STORAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "site_database.json")

def init_storage():
    """
    Depolama dosyasını oluştur (yoksa)
    
    Bu fonksiyon, ilk kullanımda veya dosya silinmişse yeni bir depolama
    dosyası oluşturur. Dosya yapısı {"sites": {}} şeklinde başlatılır.
    """
    if not os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "w") as f:
            json.dump({"sites": {}}, f)

def get_all_sites():
    """
    Tüm kayıtlı siteleri getir
    
    Depolama dosyasından tüm sitelerin bilgilerini okur ve döndürür.
    Dosya yoksa init_storage() ile oluşturulur.
    
    Returns:
        dict: site_name -> site_info şeklinde bir sözlük
    """
    init_storage()  # Dosyanın varlığını kontrol et
    with open(STORAGE_FILE, "r") as f:
        data = json.load(f)
    return data["sites"]  # Sadece sites kısmını döndür

def get_site(site_name):
    """
    Belirli bir site bilgisini getir
    
    Verilen site adına ait bilgileri döndürür. Site yoksa None döner.
    
    Args:
        site_name (str): Bilgileri alınacak sitenin adı
        
    Returns:
        dict or None: Site bilgileri veya site yoksa None
    """
    sites = get_all_sites()
    return sites.get(site_name)  # Site yoksa None döner

def save_site(site_name, site_id, deploy_url, prompts):
    """
    Site bilgilerini kaydet/güncelle
    
    Yeni bir site kaydeder veya var olan bir sitenin bilgilerini günceller.
    Site daha önce kaydedilmişse created_at değeri korunur, değilse yeni oluşturulur.
    
    Args:
        site_name (str): Site adı
        site_id (str): Netlify site ID'si
        deploy_url (str): Site deploy URL'si
        prompts (list): Site oluşturmak için kullanılan promptların listesi
    """
    init_storage()  # Dosyanın varlığını kontrol et
    
    # Mevcut verileri oku
    with open(STORAGE_FILE, "r") as f:
        data = json.load(f)
    
    # Site bilgilerini güncelle veya yeni oluştur
    data["sites"][site_name] = {
        "site_id": site_id,                 # Netlify site ID
        "deploy_url": deploy_url,           # Site URL'si
        "prompts": prompts,                 # Prompt geçmişi
        "last_updated": datetime.now().isoformat(),  # Son güncelleme zamanı
        # Site daha önce kaydedilmişse eski oluşturma tarihini koru, değilse yeni oluştur
        "created_at": data["sites"].get(site_name, {}).get("created_at", datetime.now().isoformat())
    }
    
    # Güncellenmiş verileri kaydet (indent=2 ile daha okunaklı JSON formatı)
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)