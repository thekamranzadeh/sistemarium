import os
import requests
from datetime import datetime
from github import Github
from instagrapi import Client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- AYARLAR ---
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- MÖVZUNUZ ---
PAGE_TOPIC = "AI və onun insan psixologiyasına təsiri haqqında növbəti 10 il üçün nələr baş verəcəyi ilə bağlı düşüncələr."

def main():
    print("🚀 TAM AVTOMATİK İnstagram Botu işə düşdü...")
    
    if not all([IG_USERNAME, IG_PASSWORD, OPENAI_API_KEY, GITHUB_TOKEN, GITHUB_REPO]):
        print("❌ .env faylında məlumatlar əksikdir! Zəhmət olmasa API açarlarını yazın.")
        return

    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # 1. Mövzu İdeyası Yaratmaq
    print("🧠 1. Yeni post üçün mövzu ideyası düşünülür...")
    try:
        idea_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"Sən '{PAGE_TOPIC}' mövzusunda İnstagram səhifəsi işlədirsən. Mənə elə indicə paylaşmaq üçün maraqlı, diqqətçəkən, tək bir cümləlik İDEYA (mövzu başlığı) ver. Sual vermə, yalnız ideyanı yaz."}]
        )
        post_idea = idea_response.choices[0].message.content.strip()
        print(f"💡 İdeya tapıldı: {post_idea}")
    except Exception as e:
        print(f"❌ OpenAI Xətası (İdeya): {e}")
        return
    
    # 2. Şəkil Yaratmaq (DALL-E 3)
    print("🎨 2. OpenAI DALL-E 3 ilə vizual yaradılır (Bu 10-15 saniyə çəkə bilər)...")
    try:
        image_response = client.images.generate(
            model="dall-e-3",
            prompt=f"Aesthetic, high-quality, cinematic Instagram post visual about: '{post_idea}'. NO TEXT OR LETTERS IN THE IMAGE. Extremely beautiful, modern and atmospheric.",
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = image_response.data[0].url
    except Exception as e:
        print(f"❌ Şəkil yaradılarkən xəta: {e}")
        return

    # Şəkli lokal olaraq yükləyirik
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_img_name = f"post_{timestamp}.jpg"
    img_data = requests.get(image_url).content
    with open(local_img_name, 'wb') as handler:
        handler.write(img_data)
    print("🖼️ Şəkil generasiya edildi və yükləndi.")

    # 3. Caption (Mətn) Yaratmaq
    print("📝 3. Şəkilə uyğun Caption yazılır...")
    caption_prompt = f"""Sən '{PAGE_TOPIC}' mövzusunda paylaşımlar edirsən. 
    Aşağıdakı ideya üçün mükəmməl bir İnstagram mətni (caption) yaz.
    İdeya: {post_idea}
    
    Qaydalar: 
    - 3 qısa abzas olsun. 
    - 1-ci abzas hook (diqqətçəkən sual/cümlə). 
    - 2-ci abzas qısa izah. 
    - 3-cü abzas call-to-action (rəyə çağırış). 
    - Maksimum 50-70 söz. 3-4 emoji. Sonda 5 populyar hashtag. 
    - Dil: Qrammatik düzgün və axıcı Azərbaycan dili."""
    
    try:
        caption_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": caption_prompt}]
        )
        caption = caption_response.choices[0].message.content.strip()
        print(f"📜 Hazır Mətn:\n{caption}\n")
    except Exception as e:
        print(f"❌ OpenAI Xətası (Caption): {e}")
        return

    # 4. İnstagram-a Paylaşmaq
    print("📱 4. İnstagram-a bağlanır...")
    cl = Client()
    
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    
    try:
        # Sessiyanı GitHub-dan yükləməyə çalışırıq (Ban riskinin qarşısını almaq üçün)
        try:
            session_file = repo.get_contents("session.json")
            with open("session.json", "wb") as f:
                f.write(session_file.decoded_content)
            cl.load_settings("session.json")
            cl.login(IG_USERNAME, IG_PASSWORD)
            print("✅ Mövcud sessiya yükləndi (Təhlükəsiz giriş).")
        except:
            # Sessiya yoxdursa, sıfırdan girib GitHub-a yadda saxlayırıq
            cl.login(IG_USERNAME, IG_PASSWORD)
            cl.dump_settings("session.json")
            with open("session.json", "r") as f:
                session_data = f.read()
            repo.create_file("session.json", "Save IG session", session_data)
            print("✅ Yeni sessiya yaradıldı və GitHub-a saxlanıldı.")
            
        print("✅ Hesaba daxil olundu. Paylaşılır...")
        cl.photo_upload(local_img_name, caption)
        print("🎉 POST İNSTAGRAMDA UĞURLA PAYLAŞILDI!")
    except Exception as e:
        print(f"❌ İnstagram Xətası: {e}")
        return

    # 5. Şəkli GitHub-da "images" qovluğunda Arxivləmək
    print("🔄 5. Şəkil GitHub arxivinə yüklənir...")
    try:
        repo.create_file(f"images/{local_img_name}", f"Avtomatik post: {post_idea}", img_data)
        print("✅ Şəkil GitHub-da arxivləşdirildi.")
    except Exception as e:
        print(f"⚠️ GitHub-a yükləmədə problem (amma post paylaşıldı): {e}")

    # Təmizlik
    if os.path.exists(local_img_name):
        os.remove(local_img_name)
    if os.path.exists("session.json"):
        os.remove("session.json")
        
    print("🚀 BÜTÜN PROSES QÜSURSUZ TAMAMLANDI! Növbəti post 4 saat sonra olacaq.")

if __name__ == "__main__":
    main()
