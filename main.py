import os
import base64
import time
import random
from datetime import datetime
from github import Github
from github.GithubException import GithubException
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, LoginRequired
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TEXT_MODEL = "gpt-5.5-2026-04-23"
SMART_MODEL = "gpt-5.5-2026-04-23"
IMAGE_MODEL = "gpt-image-1"

PAGE_TOPIC = "AI və onun insan psixologiyasına təsiri haqqında növbəti 10 il üçün düşüncələr."


def setup_instagram_client():
    """İnstagram klientini təhlükəsiz parametrlərlə qurur."""
    cl = Client()
    
    # Mobil cihazı təqlid etmək
    cl.set_device({
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "android_release": "8.0.0",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "samsung",
        "device": "SM-G930F",
        "model": "herolte",
        "cpu": "samsungexynos8890",
        "version_code": "314665256",
    })
    cl.set_user_agent(
        "Instagram 269.0.0.18.75 Android (26/8.0.0; 480dpi; 1080x1920; samsung; SM-G930F; herolte; samsungexynos8890; en_US; 314665256)"
    )
    
    # Random delay − robotvari davranışı azaldır
    cl.delay_range = [2, 5]
    
    return cl


def login_to_instagram(cl, repo):
    """Sessiya ilə təhlükəsiz giriş. Challenge gəlsə xəta atır."""
    session_existed = False
    
    try:
        # Sessiyanı GitHub-dan yükləməyə çalış
        session_file = repo.get_contents("session.json")
        with open("session.json", "wb") as f:
            f.write(session_file.decoded_content)
        cl.load_settings("session.json")
        
        # Sessiyanı sınamaq − challenge olmadan
        try:
            cl.get_timeline_feed()
            print("✅ Mövcud sessiya keçərlidir.")
            session_existed = True
            return session_existed
        except LoginRequired:
            print("⚠️ Sessiya köhnəlib, yenidən giriş edilir...")
            cl.login(IG_USERNAME, IG_PASSWORD, relogin=True)
            session_existed = True
            return session_existed
            
    except GithubException:
        # Sessiya yoxdur − ilk giriş
        print("⚠️ Sessiya tapılmadı. İlk giriş edilir...")
        print("⚠️ DİQQƏT: İlk giriş üçün manual edib sessiyanı saxlamaq daha təhlükəsizdir!")
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings("session.json")
        with open("session.json", "r") as f:
            session_data = f.read()
        repo.create_file("session.json", "Save IG session", session_data)
        print("✅ Yeni sessiya yaradıldı və GitHub-a saxlandı.")
        return session_existed


def main():
    print("🚀 TAM AVTOMATİK İnstagram Botu işə düşdü...")

    if not all([IG_USERNAME, IG_PASSWORD, OPENAI_API_KEY, GITHUB_TOKEN, GITHUB_REPO]):
        print("❌ .env faylında məlumatlar əksikdir!")
        return

    client = OpenAI(api_key=OPENAI_API_KEY)

    # 1. İdeya
    print("🧠 1. Mövzu ideyası düşünülür...")
    try:
        idea_response = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{
                "role": "user",
                "content": f"Sən '{PAGE_TOPIC}' mövzusunda İnstagram səhifəsi işlədirsən. Mənə paylaşmaq üçün maraqlı, tək bir cümləlik İDEYA ver. Yalnız ideyanı yaz."
            }],
            reasoning_effort="low"
        )
        post_idea = idea_response.choices[0].message.content.strip()
        print(f"💡 İdeya: {post_idea}")
    except Exception as e:
        print(f"❌ OpenAI Xətası (İdeya): {e}")
        return

    # 2. Şəkil promptu
    print("🎨 2. Şəkil promptu hazırlanır...")
    try:
        with open("systemarium_prompt.txt", "r", encoding="utf-8") as f:
            meta_prompt = f.read()

        dalle_prompt_response = client.chat.completions.create(
            model=SMART_MODEL,
            messages=[
                {"role": "system", "content": meta_prompt},
                {"role": "user", "content": f"Topic Idea: {post_idea}. Generate the final image prompt now."}
            ],
            reasoning_effort="medium"
        )
        final_image_prompt = dalle_prompt_response.choices[0].message.content.strip()
        print(f"✨ Şəkil promptu:\n{final_image_prompt}\n")
    except FileNotFoundError:
        print("❌ systemarium_prompt.txt tapılmadı!")
        return
    except Exception as e:
        print(f"❌ OpenAI Xətası (Prompt): {e}")
        return

    # 3. Şəkil
    print("🖼️ 3. Şəkil yaradılır...")
    local_img_name = None
    img_data = None
    try:
        image_response = client.images.generate(
            model=IMAGE_MODEL,
            prompt=final_image_prompt[:4000],
            size="1024x1024",
            n=1
        )
        b64_data = image_response.data[0].b64_json

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_img_name = f"post_{timestamp}.jpg"

        img_data = base64.b64decode(b64_data)
        with open(local_img_name, "wb") as fh:
            fh.write(img_data)

        print(f"🖼️ Şəkil yükləndi: {local_img_name}")
    except Exception as e:
        print(f"❌ Şəkil xətası: {e}")
        return

    # 4. Caption
    print("📝 4. Caption yazılır...")
    caption_prompt = f"""Sən '{PAGE_TOPIC}' mövzusunda paylaşımlar edirsən.
İdeya: {post_idea}

Qaydalar:
- 3 qısa abzas
- 1-ci: hook, 2-ci: izah, 3-cü: call-to-action
- Maksimum 50-70 söz, 3-4 emoji
- Sonda 5 populyar hashtag
- Düzgün Azərbaycan dili"""

    try:
        caption_response = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": caption_prompt}],
            reasoning_effort="low"
        )
        caption = caption_response.choices[0].message.content.strip()
        print(f"📜 Caption:\n{caption}\n")
    except Exception as e:
        print(f"❌ OpenAI Xətası (Caption): {e}")
        cleanup(local_img_name)
        return

    # 5. İnstagram
    print("📱 5. İnstagram-a bağlanır...")
    cl = setup_instagram_client()
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)

    try:
        session_existed = login_to_instagram(cl, repo)
        
        # Random gözləmə − insani davranışı təqlid etmək
        wait = random.randint(5, 15)
        print(f"⏱️ {wait} saniyə gözlənilir (təhlükəsizlik üçün)...")
        time.sleep(wait)
        
        print("✅ Paylaşılır...")
        cl.photo_upload(local_img_name, caption)
        print("🎉 POST UĞURLA PAYLAŞILDI!")

        # Sessiyanı yenilə
        if session_existed:
            try:
                cl.dump_settings("session.json")
                with open("session.json", "r") as f:
                    new_session = f.read()
                contents = repo.get_contents("session.json")
                repo.update_file("session.json", "Update IG session", new_session, contents.sha)
                print("✅ Sessiya GitHub-da yeniləndi.")
            except Exception as e:
                print(f"⚠️ Sessiya yenilənmədi: {e}")

    except ChallengeRequired:
        print("❌ İnstagram CHALLENGE tələb edir!")
        print("📱 Telefonda hesaba daxil olun, bildirişdə 'Bu mən idim' seçin.")
        print("⏰ 24 saat heç bir bot kodu işlətməyin.")
        cleanup(local_img_name)
        return
    except Exception as e:
        print(f"❌ İnstagram Xətası: {e}")
        cleanup(local_img_name)
        return

    # 6. Arxiv
    print("🔄 6. Şəkil arxivlənir...")
    try:
        repo.create_file(f"images/{local_img_name}", f"Post: {post_idea}", img_data)
        print("✅ Arxivləndi.")
    except Exception as e:
        print(f"⚠️ Arxivləmə problemi: {e}")

    cleanup(local_img_name)
    print("🚀 PROSES TAMAMLANDI!")


def cleanup(img_name):
    if img_name and os.path.exists(img_name):
        os.remove(img_name)
    if os.path.exists("session.json"):
        os.remove("session.json")


if __name__ == "__main__":
    main()
