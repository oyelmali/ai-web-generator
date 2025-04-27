import streamlit as st
import requests
import datetime
import json
import re

# Backend API'sine bağlantı URL'si - geliştirme ortamında localhost kullanılıyor
BACKEND_URL = "http://localhost:8000"

# Uygulama başlığı ve açıklaması
st.title("AI ile Web Sitesi Oluşturucu")
st.markdown("Yapay zeka ile birkaç komut kullanarak web sitenizi oluşturun")

# Session (oturum) durumunu kontrol et ve tanımla
# Streamlit her çalıştığında yeniden başlatılır, bu yüzden durum session_state'te saklanmalıdır
if 'deploy_url' not in st.session_state:
    st.session_state.deploy_url = ""  # Siteye erişim URL'si
if 'site_name' not in st.session_state:
    st.session_state.site_name = ""   # Site adı
if 'site_id' not in st.session_state:
    st.session_state.site_id = ""     # Netlify site ID'si
if 'site_checked' not in st.session_state:
    st.session_state.site_checked = False  # Site adı kontrol edildi mi?
if 'history' not in st.session_state:
    st.session_state.history = ""     # İşlem geçmişi logu
if 'prompts' not in st.session_state:
    st.session_state.prompts = []     # Kullanıcının girdiği prompt'lar
if 'setup_stage' not in st.session_state:
    # Site kurulum aşaması: initial (başlangıç), domain_verification (domain doğrulama), 
    # ssl_setup (SSL kurulumu), completed (tamamlandı)
    st.session_state.setup_stage = "initial"

# Site adı kontrolü ve bilgileri yükleme fonksiyonu
def check_site_name():
    """
    Kullanıcının girdiği site adını kontrol eder ve varsa mevcut site bilgilerini yükler
    
    Bu fonksiyon, text_input'tan st.session_state.site_name_input'u alır,
    backend'e bir istek gönderir ve sitenin var olup olmadığını kontrol eder.
    Varsa, site bilgilerini session state'e yükler.
    """
    site_name = st.session_state.site_name_input.strip()
    if not site_name:
        st.error("Lütfen bir site adı girin!")
        return
    
    with st.spinner("Site bilgileri kontrol ediliyor..."):
        try:
            # Backend API'ye site adı kontrolü için istek gönder
            response = requests.post(
                f"{BACKEND_URL}/api/check_site_name", 
                json={"site_name": site_name}
            )
            data = response.json()
            
            # Session state'i güncelle
            st.session_state.site_name = site_name
            st.session_state.site_checked = True
            
            if data["exists"]:
                # Site zaten varsa, bilgilerini yükle
                st.success(data["message"])
                
                # Mevcut site bilgilerini session state'e yükle
                if data.get("site_id"):
                    st.session_state.site_id = data["site_id"]
                
                if data.get("deploy_url"):
                    st.session_state.deploy_url = data["deploy_url"]
                
                if data.get("prompts"):
                    st.session_state.prompts = data["prompts"]
                    prompt_history = "\n".join([f"- {p}" for p in data["prompts"]])
                    st.session_state.prompt_history = prompt_history
            else:
                # Site yoksa bilgilendirme mesajı göster
                st.info(data["message"])
                
        except Exception as e:
            # Bağlantı hatası durumunda kullanıcıya bildir
            st.error(f"Bağlantı hatası: {str(e)}")

# Domain doğrulama fonksiyonu
def verify_domain(domain):
    """
    Girilen domain adını doğrular
    
    Args:
        domain (str): Doğrulanacak domain adı
        
    Returns:
        tuple: (başarılı mı (bool), mesaj (str))
    """
    # Basit regex ile domain formatı doğrulaması
    if not re.match(r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$', domain):
        return False, "Geçersiz domain formatı. Örnek: example.com"
    
    try:
        # Backend API'ye domain doğrulama isteği gönder
        response = requests.post(
            f"{BACKEND_URL}/api/verify_domain", 
            json={"domain": domain}
        )
        data = response.json()
        
        if data["status"] == "ok":
            return True, data["message"]
        else:
            return False, data["message"]
    except Exception as e:
        return False, f"Domain doğrulama hatası: {str(e)}"

# Domain ekleme fonksiyonu
def add_domain(domain):
    """
    Netlify sitesine özel domain ekler
    
    Args:
        domain (str): Eklenecek domain adı
        
    Returns:
        tuple: (başarılı mı (bool), mesaj (str))
    """
    try:
        # Backend API'ye domain ekleme isteği gönder
        response = requests.post(
            f"{BACKEND_URL}/api/add_domain", 
            json={"domain": domain}
        )
        data = response.json()
        
        if data["status"] == "ok":
            # Domain başarıyla eklendiyse bir sonraki aşamaya geç
            st.session_state.setup_stage = "ssl_setup"
            return True, data["message"]
        else:
            return False, data["message"]
    except Exception as e:
        return False, f"Domain ekleme hatası: {str(e)}"

# SSL kurulum fonksiyonu
def setup_ssl():
    """
    Netlify sitesi için SSL sertifikasını kurar
    
    Returns:
        tuple: (başarılı mı (bool), mesaj (str))
    """
    try:
        # Backend API'ye SSL kurulumu isteği gönder
        response = requests.post(
            f"{BACKEND_URL}/api/setup_ssl", 
            json={"site_id": st.session_state.site_id}
        )
        data = response.json()
        
        if data["status"] == "ok":
            # SSL kurulumu başarılıysa kurulum aşamasını tamamlandı olarak işaretle
            st.session_state.setup_stage = "completed"
            if data.get("ssl_url"):
                st.session_state.deploy_url = data["ssl_url"]
            return True, data["message"]
        else:
            return False, data["message"]
    except Exception as e:
        return False, f"SSL kurulum hatası: {str(e)}"

# Adım göstergesi - kurulum aşamasını görsel olarak gösterir
def show_progress_steps():
    """
    Site kurulum aşamalarını adım adım görsel olarak gösterir
    Yalnızca kurulum aşamasında (domain veya SSL) gösterilir
    """
    # Sadece kurulum aşamasındayken göster
    if st.session_state.setup_stage not in ["domain_verification", "ssl_setup", "completed"]:
        return
    
    # Adımları göster
    st.write("### Site Yayımlama Adımları")
    
    # Üç adımlı görsel ilerleme göstergesi
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.session_state.setup_stage in ["domain_verification", "ssl_setup", "completed"]:
            st.success("1. Site Oluşturma ✓")  # Tamamlandı
        else:
            st.info("1. Site Oluşturma")  # Aktif
    
    with col2:
        if st.session_state.setup_stage in ["ssl_setup", "completed"]:
            st.success("2. Domain Ayarları ✓")  # Tamamlandı
        elif st.session_state.setup_stage == "domain_verification":
            st.info("2. Domain Ayarları")  # Aktif
        else:
            st.write("2. Domain Ayarları")  # Henüz aktif değil
    
    with col3:
        if st.session_state.setup_stage == "completed":
            st.success("3. SSL/HTTPS Kurulumu ✓")  # Tamamlandı
        elif st.session_state.setup_stage == "ssl_setup":
            st.info("3. SSL/HTTPS Kurulumu")  # Aktif
        else:
            st.write("3. SSL/HTTPS Kurulumu")  # Henüz aktif değil

# Site onaylama işlemi - aşamalı olarak kullanıcıyı adım adım yönlendirir
def approve_site():
    """
    Site onaylama ve yayınlama işlemini aşamalı olarak yürütür
    
    Bu fonksiyon, site kurulumunun farklı aşamalarını yönetir:
    1. Başlangıç (initial) -> Domain doğrulama aşamasına geçiş
    2. Domain doğrulama (domain_verification) -> Domain ekleme veya atlamanın işlenmesi
    3. SSL kurulumu (ssl_setup) -> SSL sertifikası kurulumu
    4. Tamamlandı (completed) -> Final bilgileri ve seçenekleri gösterme
    """
    # Site adı kontrolü
    if not st.session_state.site_name or not st.session_state.site_id:
        st.error("Site bilgileri eksik. Lütfen geçerli bir site oluşturun.")
        return
    
    # Adım göstergesini göster
    show_progress_steps()
    
    # Başlangıç aşaması - ilk onay tıklamasında domain doğrulama aşamasına geç
    if st.session_state.setup_stage == "initial":
        st.session_state.setup_stage = "domain_verification"
        st.rerun()  # Sayfayı yeniden yükle
    
    # Domain doğrulama aşaması UI
    elif st.session_state.setup_stage == "domain_verification":
        st.subheader("Domain Ayarları")
        st.info("Sitenizi özel bir domain ile kullanmak isterseniz, lütfen domain adını girin. Sadece Netlify subdomain'i kullanmak için boş bırakabilirsiniz.")
        
        # Domain girişi
        domain = st.text_input(
            "Var olan domain adınızı girin (isteğe bağlı)", 
            help="Örnek: example.com"
        )
        
        # Butonlar
        col1, col2, col3 = st.columns(3)
        
        # Geri dön butonu
        with col1:
            if st.button("← Geri Dön", key="back_from_domain"):
                st.session_state.setup_stage = "initial"
                st.rerun()
        
        # Domain kullanmadan devam et butonu
        with col2:
            if st.button("Domain Kullanmadan Devam Et"):
                st.session_state.setup_stage = "ssl_setup"
                st.rerun()
        
        # Domain ekle butonu - domain girilmediyse devre dışı bırak
        with col3:
            if st.button("Domain Ekle", type="primary", disabled=not domain):
                if domain:
                    # Domain formatını doğrula
                    valid, message = verify_domain(domain)
                    if valid:
                        # Domain ekle
                        success, add_message = add_domain(domain)
                        if success:
                            st.success(add_message)
                            st.session_state.custom_domain = domain
                            st.rerun()
                        else:
                            st.error(add_message)
                    else:
                        st.error(message)
    
    # SSL kurulum aşaması
    elif st.session_state.setup_stage == "ssl_setup":
        st.subheader("SSL/HTTPS Kurulumu")
        st.info("Sitenizin güvenli (HTTPS) olarak hizmet vermesi için SSL sertifikası kurulacak.")
        
        col1, col2 = st.columns(2)
        
        # Geri dön butonu
        with col2:
            if st.button("← Geri Dön", key="back_from_ssl"):
                st.session_state.setup_stage = "domain_verification"
                st.rerun()
        
        # SSL kurulumu başlat butonu
        with col1:
            if st.button("SSL Kurulumunu Başlat", type="primary"):
                with st.spinner("SSL sertifikası oluşturuluyor ve site güvenliği sağlanıyor..."):
                    # SSL kurulumunu başlat
                    success, message = setup_ssl()
                    if success:
                        st.success(message)
                        st.balloons()  # Kutlama efekti
                        st.rerun()
                    else:
                        st.error(message)
                        # Hata durumunda manuel yönlendirme
                        netlify_admin_url = f"https://app.netlify.com/sites/{st.session_state.site_name}/overview"
                        st.warning("SSL kurulumu otomatik olarak tamamlanamadı. Netlify Kontrol Panelinden manuel olarak tamamlayabilirsiniz.")
                        st.markdown(f"[Netlify Kontrol Paneline Git]({netlify_admin_url})")
    
    # Kurulum tamamlandı - final bilgilerini göster
    elif st.session_state.setup_stage == "completed":
        st.success("🎉 Tebrikler! Siteniz Tamamen Kuruldu")
        st.markdown(f"**Site URL:** [{st.session_state.deploy_url}]({st.session_state.deploy_url})")
        
        # Site bilgileri
        st.info("Site Bilgileri:")
        st.markdown(f"- **Site Adı:** {st.session_state.site_name}")
        if hasattr(st.session_state, 'custom_domain'):
            st.markdown(f"- **Özel Domain:** {st.session_state.custom_domain}")
        st.markdown(f"- **Netlify URL:** {st.session_state.deploy_url}")
        
        # Netlify kontrol paneli linki
        netlify_admin_url = f"https://app.netlify.com/sites/{st.session_state.site_name}/overview"
        st.markdown(f"[Netlify Kontrol Panelini Aç]({netlify_admin_url})")
        
        # Başa dön butonu
        if st.button("Düzenlemeye Geri Dön"):
            st.session_state.setup_stage = "initial"
            st.rerun()

# Ana uygulama konteynerı
with st.container():
    # İki aşamalı form: İlk önce site adı, sonra prompt
    
    # 1. Adım: Site adı girişi ve kontrolü
    if not st.session_state.site_checked:
        st.subheader("1. Adım: Site Adı Belirleyin")
        
        # Site adı girişi (input field)
        st.text_input(
            "Site Adı (örn. restoran-sitem)", 
            key="site_name_input",
            help="Sadece harfler, rakamlar ve tire (-) kullanabilirsiniz"
        )
        
        # Site adını kontrol etme butonu 
        st.button("Site Adını Kontrol Et", on_click=check_site_name)
        
        # Kayıtlı siteler listesi - kullanıcıya kolaylık sağlar
        try:
            # Backend API'den kayıtlı siteleri getir
            sites_resp = requests.get(f"{BACKEND_URL}/api/sites")
            if sites_resp.status_code == 200:
                sites = sites_resp.json().get("sites", {})
                if sites:
                    st.subheader("Kayıtlı Siteleriniz")
                    # Her site için bir satır göster
                    for site_name, site_info in sites.items():
                        last_updated = site_info.get("last_updated", "").split("T")[0]  # Tarih kısmını al
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{site_name}** - Son güncelleme: {last_updated}")
                        with col2:
                            # Site seçme butonu
                            if st.button("Seç", key=f"select_{site_name}"):
                                st.session_state.site_name_input = site_name
                                check_site_name()
        except Exception as e:
            st.warning(f"Kayıtlı siteler yüklenemedi: {str(e)}")
    
    # 2. Adım: Prompt girişi ve site oluşturma
    else:
        st.subheader(f"2. Adım: Web Sitesi Oluşturma - {st.session_state.site_name}")
        
        # Eğer site kurulum aşamasındaysa
        if st.session_state.setup_stage != "initial":
            approve_site()  # Mevcut aşamayı göster
        else:
            # Normal site oluşturma/düzenleme arayüzü
            # Önceki promptları göster (eğer varsa)
            if st.session_state.prompts:
                with st.expander("Önceki Promptlar", expanded=False):
                    for i, prompt in enumerate(st.session_state.prompts):
                        st.markdown(f"**Prompt {i+1}:** {prompt}")
            
            # Prompt girişi - kullanıcı buraya site için isteklerini yazar
            prompt = st.text_area(
                "Web Siteniz Nasıl Olsun?", 
                placeholder="Örnek: Bir restoran sitesi oluştur, menü sağda olsun ve tema renkleri pastel tonlarda olsun",
                height=150
            )
            
            # Butonlar - site oluşturma ve yönetim seçenekleri
            col1, col2, col3, col4 = st.columns(4)
            
            # Oluştur/Güncelle butonu - prompt'a göre siteyi oluşturur veya günceller
            with col1:
                if st.button("Oluştur/Güncelle", type="primary", disabled=not prompt):
                    with st.spinner("AI sitenizi oluşturuyor..."):
                        try:
                            # Backend API'ye prompt gönder
                            payload = {
                                "prompt": prompt,
                                "site_name": st.session_state.site_name
                            }
                            
                            response = requests.post(f"{BACKEND_URL}/api/prompt", json=payload)
                            data = response.json()
                            
                            if data["status"] == "ok":
                                # Başarılı yanıt - site URL ve bilgilerini güncelle
                                st.session_state.deploy_url = data["deploy_url"]
                                # Site ID'sini de kaydet (domain ve SSL kurulumu için gerekli)
                                if "site_id" in data:
                                    st.session_state.site_id = data["site_id"]
                                
                                st.session_state.prompts.append(prompt)  # Prompt'u geçmişe ekle
                                
                                # İşlem geçmişini güncelle - debugging ve ilerleme takibi için
                                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                                st.session_state.history += f"[{timestamp}] Prompt: {prompt}\n"
                                st.session_state.history += f"[{timestamp}] Yanıt: {data['message']}\n\n"
                                
                                st.success(f"Site oluşturuldu: {data['message']}")
                            else:
                                st.error(f"Hata: {data['message']}")
                                
                        except Exception as e:
                            st.error(f"Bağlantı hatası: {str(e)}")
            
            # Siteyi Onayla butonu - kurulum aşamasına geçer
            with col2:
                if st.button("Siteyi Onayla", type="primary", disabled=not st.session_state.deploy_url):
                    approve_site()
            
            # Yeni Siteye Başla butonu - session'ı sıfırlayarak yeni siteye başlar
            with col3:
                if st.button("Yeni Siteye Başla"):
                    # Session state'i sıfırla
                    st.session_state.site_checked = False
                    st.session_state.deploy_url = ""
                    st.session_state.site_name = ""
                    st.session_state.site_id = ""
                    st.session_state.prompts = []
                    st.session_state.setup_stage = "initial"
                    
                    # Backend session'ı da sıfırla
                    try:
                        requests.post(f"{BACKEND_URL}/api/reset")
                    except:
                        pass
                    
                    st.rerun()
            
            # Siteyi Temizle butonu - mevcut site içeriğini sıfırlar ama aynı site adını korur
            with col4:
                if st.button("Siteyi Temizle"):
                    # Prompt geçmişini sıfırla
                    st.session_state.prompts = []
                    # Site verilerini sıfırla ama site adını koru
                    try:
                        response = requests.post(f"{BACKEND_URL}/api/reset_site_content", 
                                                json={"site_name": st.session_state.site_name})
                        if response.status_code == 200:
                            st.success("Site içeriği temizlendi. Yeni prompt girebilirsiniz.")
                            st.session_state.prompts = []
                            st.rerun()
                        else:
                            st.error("Site içeriği temizlenirken hata oluştu.")
                    except Exception as e:
                        st.error(f"Bağlantı hatası: {str(e)}")

            # Site önizleme - eğer bir URL varsa iframe içinde göster
            if st.session_state.deploy_url:
                st.subheader("Site Önizleme")
                # iframe kullanarak site önizlemesini göster
                st.components.v1.iframe(st.session_state.deploy_url, height=500)
                
                # URL'yi göster
                st.success(f"Site URL: {st.session_state.deploy_url}")
                
                # URL'yi açma butonu - yeni sekmede tam boyutta görüntülemek için
                st.markdown(f"[Siteyi Yeni Sekmede Aç]({st.session_state.deploy_url})")

                # Ayırıcı çizgi
                st.write("---")
                

# İşlem geçmişi - tüm işlemlerin log'unu gösterir
if st.session_state.history:
    with st.expander("İşlem Geçmişi", expanded=False):
        st.text_area("", value=st.session_state.history, height=200, disabled=True)

# Yardım bölümü - kullanıcıya nasıl kullanılacağını açıklar
with st.expander("Nasıl Kullanılır", expanded=False):
    st.markdown("""
    ## Nasıl Kullanılır
    1. **Site Adı**: Sitenizin benzersiz adını girin ve kontrol edin
    2. **Kayıtlı Siteler**: Daha önce oluşturduğunuz siteleri görebilir ve seçebilirsiniz
    3. **Komut Girin**: Sitenizin nasıl olmasını istediğinizi açıklayın
    4. **Oluştur/Güncelle**: AI'ın sitenizi oluşturmasını bekleyin
    5. **Önizleme**: Oluşturulan siteyi inceleyin
    6. **Revizyon**: Değişiklikler istiyorsanız, yeni bir komut girin ve 'Oluştur/Güncelle' butonuna tıklayın
    7. **Siteyi Yayımla**: Siteniz hazır olduğunda yayımlama sürecini başlatın:
        - Domain Ayarları: İsterseniz özel domain ekleyin
        - SSL/HTTPS Kurulumu: Sitenizi güvenli hale getirin
    
    **İpucu**: Detaylı komutlar daha iyi sonuçlar verir. Renkleri, düzeni ve içeriği açıkça belirtin.
    """)

# Arayüz footer ve telif hakkı bilgisi
st.markdown("---")
st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>AI Web Sitesi Oluşturucu</div>", unsafe_allow_html=True)

# Durum çubuğu (alt kısımda) - mevcut site ve durumunu gösterir
if st.session_state.site_name:
    # Mevcut site bilgilerini göster
    current_site_info = f"Aktif Site: {st.session_state.site_name}"
    if st.session_state.deploy_url:
        current_site_info += f" | URL: {st.session_state.deploy_url}"
    
    # Mevcut durum göstergesi - sitenin hangi aşamada olduğunu belirtir
    if st.session_state.setup_stage == "completed":
        status = "Yayımlandı ✓"
    elif st.session_state.setup_stage == "ssl_setup":
        status = "SSL Kurulumu Bekliyor"
    elif st.session_state.setup_stage == "domain_verification":
        status = "Domain Ayarları Bekliyor"
    elif st.session_state.deploy_url:
        status = "Düzenleniyor"
    else:
        status = "Oluşturulmadı"
    
    current_site_info += f" | Durum: {status}"
    
    # Sabit durum çubuğu olarak göster (fixed position)
    st.markdown(f"<div style='position: fixed; bottom: 0; width: 100%; background-color: #f0f2f6; padding: 5px; text-align: center;'>{current_site_info}</div>", unsafe_allow_html=True)