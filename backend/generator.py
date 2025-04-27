import os
import re
from llama_cpp import Llama

# Model yolu - doğru yolu kullanın ve raw string (r"...") olarak tanımlayın
# Raw string kullanımı Windows path'lerindeki ters slash (\) karakterlerinin escape karakter olarak algılanmasını önler
MODEL_PATH = r"C:\Users\oyelmali\Desktop\eterna-case\models--NikolayKozloff--Nxcode-CQ-7B-orpo-Q6_K-GGUF\blobs\6378a0cac8a8c5d94e85273fe534fd095fc9d5b558b35b815107771e7d1c1107"

# Eski model ve CLI yolları (fallback olarak saklanabilir)
# Eğer birincil model yüklenemezse bu alternatif model ve CLI kullanılacak
OLD_MODEL_PATH = r"C:\Users\oyelmali\Desktop\eterna-case\models--TheBloke--CodeLlama-7B-Instruct-GGUF\snapshots\2f064ee0c6ae3f025ec4e392c6ba5dd049c77969\codellama-7b-instruct.Q4_K_M.gguf"
OLD_LLAMA_CLI = r"C:\Users\oyelmali\Desktop\eterna-case\project\llama.cpp\build\bin\Release\llama-cli.exe"

# Model yükleme - uygulama başladığında bir kere yapılır
# Bu adım önemlidir çünkü her istek için modeli tekrar yüklemek performans açısından verimsiz olur
print("Model yükleniyor...")
try:
    model = Llama(
        model_path=MODEL_PATH,
        n_ctx=4096,       # Context size - modelin bir seferde işleyebileceği token sayısı
        n_gpu_layers=-1,  # Tüm GPU katmanlarını kullan (-1 parametresi tüm katmanları GPU'ya yükler)
        verbose=True      # Verbose çıktı - yükleme sürecinde detaylı bilgi verir
    )
    print("Model başarıyla yüklendi!")
except Exception as e:
    # Model yükleme hatası durumunda fallback mekanizmasını devreye sokmak için
    print(f"Model yükleme hatası: {e}")
    model = None
    print("Model yüklenemedi, alternatif yöntem kullanılacak.")

def combine_prompts(prompts):
    """
    Tüm promptları birleştirir
    
    İlk prompt temel istek olarak kabul edilir, sonraki promptlar revizyon olarak eklenir
    Örn: "Bir blog sitesi oluştur" + "Revizyon: Mavi tema olsun" + "Revizyon: Sosyal medya linkleri ekle"
    
    Args:
        prompts (list): Prompt listesi
    
    Returns:
        str: Birleştirilmiş prompt
    """
    base = prompts[0]  # İlk prompt temel istek
    revisions = prompts[1:]  # Diğer promptlar revizyon olarak değerlendirilir
    rev_text = ""
    for rev in revisions:
        rev_text += " Revizyon: " + rev
    return base + rev_text

def extract_html(text):
    """
    HTML içeriğini metin içinden çıkarır
    
    Model genellikle HTML koduyla birlikte açıklamalar da verebilir. Bu fonksiyon,
    sadece HTML kodunu ayıklayarak kullanılabilir bir web sayfası elde etmeyi sağlar.
    
    Metinde HTML kodu aramak için üç farklı regex deseni denenir:
    1. <!DOCTYPE html> ile başlayan tam HTML dokumanı
    2. <html> etiketi içeren HTML dokumanı
    3. <body> etiketi içeren HTML parçası (bu durumda eksik kısımlar tamamlanır)
    
    Args:
        text (str): Model tarafından üretilen metin
    
    Returns:
        str: Ayıklanmış HTML kodu
    """
    # 1. Tam HTML dokumanı (doctype) ile arama
    m = re.search(r"<!DOCTYPE html>.*?</html>", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(0)
    
    # 2. HTML tag'leri ile arama yapmayı dene (doctype yoksa)
    m = re.search(r"<html.*?>.*?</html>", text, re.DOTALL | re.IGNORECASE)
    if m:
        return "<!DOCTYPE html>\n" + m.group(0)
        
    # 3. Body tag'leri ile arama yapmayı dene (html etiketi yoksa)
    m = re.search(r"<body.*?>.*?</body>", text, re.DOTALL | re.IGNORECASE)
    if m:
        # Eksik html ve head etiketlerini ekle
        return f"<!DOCTYPE html>\n<html>\n<head>\n<meta charset='UTF-8'>\n<title>Generated Page</title>\n</head>\n{m.group(0)}\n</html>"
    
    return text  # HTML bulunamadı, tüm içeriği kullan (son çare)

def generate_html_with_history(prompts):
    """
    llama-cpp-python kullanarak HTML kodu üretir
    
    Bu fonksiyon, verilen promptları kullanarak AI modeli ile HTML kodu oluşturur.
    Öncelikli olarak llama-cpp-python API'sini kullanır, hata olursa CLI'a düşer.
    
    Args:
        prompts (list[str]): Kullanıcı promptları listesi
    
    Returns:
        str: Oluşturulan HTML içeriği
    
    Raises:
        ValueError: Prompt listesi boşsa hata verir
    """
    if not prompts:
        raise ValueError("En az bir prompt(komut) verilmelidir.")

    # Promptları birleştir
    final_prompt = combine_prompts(prompts)
    
    # Prompt'a daha net bir yönlendirme ekle
    # Bu ekleme, modele daha net talimatlar vererek istenen çıktıyı alma olasılığını artırır
    enriched_prompt = (
         f"{final_prompt}\n\n"
        "Lütfen tam ve çalışan bir HTML kodu ile cevap ver. "
        "Kodu tam ve eksiksiz olarak yaz. <!DOCTYPE html> ile başla ve tüm HTML, CSS, JavaScript kodunu içer. "
        "Sayfayı responsive tasarla ve modern tasarım prensiplerini kullan. "
        "Açıklamalar veya gerekçeler ekleme, doğrudan çalışan kodu ver."
    )
    
    print("\n[AI modeli HTML kodu üretiyor...]\n")
    
    # Model yüklenmiş ve çalışıyor mu kontrol et
    if model is not None:
        try:
            # llama-cpp-python API'si ile chat completion çağrısı yap
            response = model.create_chat_completion(
                messages=[
                    {"role": "user", "content": enriched_prompt}
                ],
                temperature=0.7,        # Yaratıcılık parametresi (0-1 arası)
                max_tokens=4000,        # Üretilecek maksimum token sayısı
                repeat_penalty=1.1,     # Tekrarları önlemek için ceza faktörü
                top_k=40,               # Olasılık dağılımında dikkate alınacak en iyi k token
                top_p=0.95              # Nucleus sampling parametresi, çeşitliliği kontrol eder
            )
            
            html_output = response["choices"][0]["message"]["content"]
            print("Model yanıtı alındı!")
            
        except Exception as e:
            # API çağrısı başarısız olursa CLI'a düş
            print(f"Model çalıştırma hatası: {e}")
            return generate_html_with_cli(prompts)  # Fallback
    else:
        # Model yüklenemediyse CLI kullanalım
        return generate_html_with_cli(prompts)
    
    # HTML içeriğini çıkar
    html_content = extract_html(html_output)
    
    # HTML dosyasını kaydet (yerel geliştirme ve debug için)
    os.makedirs("website", exist_ok=True)  # website klasörü yoksa oluştur
    with open("website/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ HTML dosyası 'website/index.html' olarak kaydedildi.")

    return html_content

def generate_html_with_cli(prompts):
    """
    Eski CLI temelli yöntem (fallback olarak)
    
    Ana API yöntemi başarısız olursa, bu fonksiyon komut satırı arabirimi aracılığıyla
    modeli çalıştırarak HTML kodu üretir. Bu, sistem dirençliliği için önemli bir yedek mekanizmadır.
    
    Args:
        prompts (list[str]): Kullanıcı promptları listesi
    
    Returns:
        str: Oluşturulan HTML içeriği
    
    Raises:
        ValueError: Prompt listesi boşsa hata verir
    """
    import subprocess
    
    if not prompts:
        raise ValueError("En az bir prompt(komut) verilmelidir.")

    # Promptları birleştir
    final_prompt = combine_prompts(prompts)
    
    # CLI komutunu hazırla
    command = [
        OLD_LLAMA_CLI,           # CLI yürütülebilir dosyası
        "-m", OLD_MODEL_PATH,    # Model dosyası
        "-p", final_prompt,      # Prompt
        "-n", "4096"             # Maksimum token sayısı
    ]
    print("\n[AI modeli HTML kodu üretiyor (CLI yöntemi)...]\n")
    
    # Alt süreci başlat ve çıktıyı bekle
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Çıktıyı UTF-8'e dönüştür, hata olursa hataları görmezden gel
    try:
        html_output = result.stdout.decode('utf-8')
    except UnicodeDecodeError:
        html_output = result.stdout.decode('utf-8', errors='ignore')

    # HTML içeriğini çıkar
    html_content = extract_html(html_output)

    # HTML dosyasını kaydet
    os.makedirs("website", exist_ok=True)
    with open("website/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ HTML dosyası 'website/index.html' olarak kaydedildi (CLI yöntemi).")

    return html_content