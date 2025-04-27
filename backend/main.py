from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import traceback

import generator  # Site HTML içeriğini oluşturan modül
import deploy     # Netlify deployment işlemlerini yöneten modül
import site_storage  # Site verilerini persistent olarak saklayan modül

app = FastAPI()

# CORS ayarları - Farklı domainlerden gelen isteklere izin vermek için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tüm originlere izin ver
    allow_credentials=True,  # Cookie ve authorization header'lar için
    allow_methods=["*"],    # Tüm HTTP metodlarına izin ver (GET, POST, etc.)
    allow_headers=["*"],    # Tüm HTTP headerlarına izin ver
)

# Kullanıcı oturumu için hafif durum yönetimi sınıfı
# Bu sınıf, uygulama çalıştığı sürece geçerli olan oturum bilgilerini tutar
class UserSession:
    def __init__(self):
        self.last_code = ""    # Son oluşturulan HTML kodu
        self.site_name = ""    # Sitenin adı
        self.site_id = ""      # Netlify'daki site ID'si
        self.deploy_url = ""   # Netlify deploy URL'i
        self.prompts = []      # Kullanıcının gönderdiği prompt geçmişi

# Global session nesnesi - Tüm uygulamada kullanılacak tek oturum
session = UserSession()

# API istekleri için Pydantic model tanımları
class PromptRequest(BaseModel):
    prompt: str                # Kullanıcının gönderdiği içerik isteği
    site_name: Optional[str] = None  # Site adı (opsiyonel)

class ApproveRequest(BaseModel):
    approve: bool              # Kullanıcı sitenin onayını verdi mi?

class SiteNameRequest(BaseModel):
    site_name: str             # Sorgulanacak site adı

class SiteInfoResponse(BaseModel):
    exists: bool               # Site zaten var mı?
    site_id: Optional[str] = None  # Varsa site ID'si
    deploy_url: Optional[str] = None  # Varsa deploy URL'i
    prompts: Optional[List[str]] = None  # Varsa önceki promptlar
    message: str               # İşlem sonuç mesajı

@app.post("/api/check_site_name", response_model=SiteInfoResponse)
async def check_site_name(req: SiteNameRequest):
    """
    Site adını kontrol eden endpoint
    - Site adının geçerliliğini doğrular
    - Yerel depolamada ve Netlify'da site varlığını kontrol eder
    - Eğer site varsa bilgilerini döndürür
    """
    try:
        site_name = req.site_name.strip().lower()
        
        # Site adı format kontrolü - sadece alfanümerik karakterler ve tire içerebilir
        if not all(c.isalnum() or c == '-' for c in site_name):
            return SiteInfoResponse(
                exists=False,
                message="Site adı sadece harfler, rakamlar ve tire (-) içerebilir."
            )
        
        # Yerel depolamada site var mı? Varsa bilgileri getir
        local_site = site_storage.get_site(site_name)
        if local_site:
            return SiteInfoResponse(
                exists=True,
                site_id=local_site["site_id"],
                deploy_url=local_site["deploy_url"],
                prompts=local_site["prompts"],
                message="Bu site daha önce oluşturulmuş. Bilgileri yüklendi."
            )
        
        # Yerel depoda yoksa Netlify'da var mı kontrol et
        existing_site_id = deploy.find_existing_site(site_name)
        if existing_site_id:
            # Site Netlify'da var ama yerel kayıtta yok - belki farklı bir cihazdan oluşturulmuş
            return SiteInfoResponse(
                exists=True,
                site_id=existing_site_id,
                message="Bu site Netlify'da bulundu, ancak yerel kayıtlarda değil. Devam ederseniz siteyi güncelleyebilirsiniz."
            )
        
        # Site adı benzersiz ve kullanılabilir
        return SiteInfoResponse(
            exists=False,
            message="Bu site adı kullanılabilir. Devam edebilirsiniz."
        )
        
    except Exception as e:
        # Hata durumunda detayları logla ve hata mesajı döndür
        traceback.print_exc()
        return SiteInfoResponse(
            exists=False,
            message=f"Site kontrolü sırasında hata: {str(e)}"
        )

@app.post("/api/prompt")
async def handle_prompt(req: PromptRequest):
    """
    Kullanıcıdan gelen prompt'u işleyen ve siteyi oluşturan/güncelleyen endpoint
    - Site adını kontrol eder
    - Prompt'a göre HTML kodu üretir
    - Netlify'a deploy eder
    - Site bilgilerini yerel depoya kaydeder
    """
    try:
        if not req.site_name:
            return {"status": "error", "message": "Site adı zorunludur."}
        
        site_name = req.site_name.strip().lower()
        
        # İlk kez mi oluşturuluyor yoksa var olan site mi güncelleniyor?
        local_site = site_storage.get_site(site_name)
        
        if local_site:
            # Var olan site için session'ı güncelle
            session.site_name = site_name
            session.site_id = local_site["site_id"]
            session.deploy_url = local_site["deploy_url"]
            session.prompts = local_site["prompts"].copy()  # Önceki promptları yükle
        else:
            # Yeni site için session'ı ayarla - site yoksa Netlify'da oluştur
            session.site_name = site_name
            session.site_id = deploy.find_or_create_site(site_name)
            session.prompts = []
        
        # Yeni prompt'u geçmişe ekle
        session.prompts.append(req.prompt)
        
        # Tüm prompt geçmişini kullanarak yeni HTML kodu üret
        html_code = generator.generate_html_with_history(session.prompts)
        session.last_code = html_code

        # Oluşturulan HTML kodunu Netlify'a deploy et
        session.deploy_url = deploy.deploy_to_site(session.site_id, html_code)
        
        # Güncellenmiş site bilgilerini yerel depoya kaydet
        site_storage.save_site(
            site_name=session.site_name,
            site_id=session.site_id,
            deploy_url=session.deploy_url,
            prompts=session.prompts
        )
        
        return {
            "status": "ok",
            "deploy_url": session.deploy_url,
            "message": "Site başarıyla oluşturuldu/güncellendi."
        }
    except Exception as e:
        # Hata durumunda detayları logla ve hata mesajı döndür
        print(f"Hata oluştu: {str(e)}")
        traceback.print_exc()
        return {"status": "error", "message": f"İşlem sırasında hata: {str(e)}"}

@app.post("/api/approve")
async def approve_site(req: ApproveRequest):
    """
    Kullanıcı site önizlemesini onayladığında çağrılan endpoint
    - Netlify'da sitenin kalıcı kurulumunu tamamlar
    - Özel ayarları yapılandırır
    - Kalıcı URL'i döndürür
    """
    try:
        if not session.site_id:
            return {
                "status": "error",
                "message": "Onaylanacak bir site bulunamadı. Lütfen önce bir site oluşturun."
            }
        
        if req.approve:
            # Kullanıcı onayladı, site kurulum işlemlerini tamamla
            final_url = deploy.finalize_site_setup(session.site_id)
            
            if final_url:
                session.deploy_url = final_url
                
                # Güncellenmiş bilgileri kaydet
                site_storage.save_site(
                    site_name=session.site_name,
                    site_id=session.site_id,
                    deploy_url=session.deploy_url,
                    prompts=session.prompts
                )
                
                return {
                    "status": "approved", 
                    "deploy_url": final_url,
                    "message": "Site kurulumu tamamlandı ve yayına alındı."
                }
            else:
                return {
                    "status": "error",
                    "deploy_url": session.deploy_url,
                    "message": "Site kurulum işlemi sırasında hata oluştu."
                }
        else:
            # Kullanıcı onaylamadı, devam et
            return {"status": "continue", "message": "Devam edebilirsiniz."}
    except Exception as e:
        # Hata durumunda detayları logla ve hata mesajı döndür
        print(f"Onay işlemi hatası: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Onay işlemi sırasında hata: {str(e)}"
        }

@app.get("/api/sites")
async def get_sites():
    """
    Tüm kayıtlı siteleri getiren endpoint
    - Yerel depodaki tüm site kayıtlarını döndürür
    """
    sites = site_storage.get_all_sites()
    return {"sites": sites}

@app.get("/api/status")
async def get_status():
    """
    Mevcut oturum durumunu getiren endpoint
    - Geçerli site adı, URL ve prompt sayısını döndürür
    """
    return {
        "site_name": session.site_name,
        "deploy_url": session.deploy_url,
        "prompts_count": len(session.prompts)
    }

@app.post("/api/reset")
async def reset_session():
    """
    Oturum bilgilerini sıfırlayan endpoint
    - Yeni oturum başlatmak için kullanılır
    """
    global session
    session = UserSession()
    return {"status": "ok", "message": "Session has been reset."}


class DomainRequest(BaseModel):
    domain: str                # Eklenecek özel alan adı

@app.post("/api/add_domain")
async def add_custom_domain(req: DomainRequest):
    """
    Siteye özel domain ekleyen endpoint
    - Domain formatını doğrular
    - Netlify'da siteye özel domain ekler
    - Birincil domain olarak ayarlar
    """
    try:
        if not session.site_id:
            return {"status": "error", "message": "Aktif bir site bulunamadı. Lütfen önce bir site oluşturun."}
        
        domain = req.domain.strip().lower()
        
        # Domain formatını regex ile kontrol et
        import re
        if not re.match(r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$', domain):
            return {"status": "error", "message": "Geçersiz domain formatı. Örnek: example.com"}
        
        # Domain'i Netlify'a ekle
        success = deploy.add_custom_domain(session.site_id, domain)
        
        if success:
            return {"status": "ok", "message": f"{domain} başarıyla eklendi ve birincil domain olarak ayarlandı."}
        else:
            return {"status": "error", "message": "Domain eklenirken bir hata oluştu. Lütfen logs'u kontrol edin."}
            
    except Exception as e:
        # Hata durumunda detayları logla ve hata mesajı döndür
        print(f"Domain ekleme hatası: {str(e)}")
        traceback.print_exc()
        return {"status": "error", "message": f"İşlem sırasında hata: {str(e)}"}
    
@app.post("/api/reset_site_content")
async def reset_site_content():
    """
    Site içeriğini sıfırlayan endpoint
    - Sitenin içeriğini varsayılan HTML ile değiştirir
    - Prompt geçmişini temizler
    - Site kaydını günceller
    """
    try:
        if not session.site_id:
            return {"status": "error", "message": "Sıfırlanacak aktif bir site bulunamadı."}
        
        # Varsayılan HTML içeriği - modern, duyarlı ve görsel olarak çekici
        varsayilan_html = """
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Site Sıfırlandı</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f5f5f5;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    padding: 20px;
                    text-align: center;
                    color: #333;
                }
                .container {
                    background-color: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
                    max-width: 600px;
                }
                h1 {
                    color: #2c3e50;
                    margin-bottom: 20px;
                }
                p {
                    font-size: 18px;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .timestamp {
                    font-size: 14px;
                    color: #7f8c8d;
                    margin-top: 20px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Bu Site Sıfırlanmıştır</h1>
                <p>Site içeriği temizlenmiş ve varsayılan haline döndürülmüştür. Yeni prompt'lar ile siteyi özelleştirebilirsiniz.</p>
            </div>
        </body>
        </html>
        """
        
        # Site içeriğini sıfırla - deploy_to_site fonksiyonu ile
        print(f"Site sıfırlanıyor: {session.site_id}")
        deploy_url = deploy.deploy_to_site(session.site_id, varsayilan_html)
        
        if deploy_url:
            # Oturumdaki site bilgilerini koru ama prompt geçmişini temizle
            old_prompts = session.prompts.copy()  # Log için saklayabilirsiniz
            session.prompts = []  # Prompt geçmişini temizle
            session.last_code = varsayilan_html
            session.deploy_url = deploy_url
            
            print(f"Site sıfırlandı, eski prompt sayısı: {len(old_prompts)}")
            
            # Kayıtlı site bilgilerini güncelle (boş prompt listesi ile)
            site_storage.save_site(
                site_name=session.site_name,
                site_id=session.site_id,
                deploy_url=session.deploy_url,
                prompts=[]  # Boş prompt listesi kaydediliyor
            )
            
            return {
                "status": "ok",
                "deploy_url": deploy_url,
                "message": "Site içeriği başarıyla sıfırlandı ve prompt geçmişi temizlendi."
            }
        else:
            return {
                "status": "error",
                "message": "Site içeriği sıfırlanamadı. Netlify servisinde bir sorun olabilir."
            }
    except Exception as e:
        # Hata durumunda detayları logla ve hata mesajı döndür
        print(f"Site içeriği sıfırlama hatası: {str(e)}")
        traceback.print_exc()
        return {"status": "error", "message": f"Sıfırlama sırasında hata: {str(e)}"}