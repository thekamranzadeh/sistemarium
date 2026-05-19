import os
import base64
from datetime import datetime
from github import Github
from github.GithubException import GithubException
from instagrapi import Client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PAGE_TOPIC = "AI və onun insan psixologiyasına təsiri haqqında növbəti 10 il üçün düşüncələr."

# Mövcud modellər (2026 may itibarilə)
TEXT_MODEL = "gpt-4o-mini"      # ucuz, sürətli mətn üçün
SMART_MODEL = "gpt-4o"           # prompt generasiyası üçün
IMAGE_MODEL = "gpt-image-1"      # şəkil generasiyası

def main():
    print("🚀 Avtomatik İnstagram Botu işə düşdü...")

    if not all([IG_USERNAME, IG_PASSWORD, OPENAI_API_KEY, GITHUB_TOKEN, GITHUB_REPO]):
        print("❌ .env faylında məlumatlar əksikdir!")
        return

    client = OpenAI(api_key=OPENAI_API_KEY)

    # 1. İdeya
    print("🧠 1. Mövzu ideyası düşünülür...")
    try:
        idea_response = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": f"Sən '{PAGE_TOPIC}' mövzusunda İnstagram səhifəsi işlədirsən. Mənə paylaşmaq üçün maraqlı, tək bir cümləlik İDEYA ver. Yalnız ideyanı yaz."}]
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
            ]
        )
        final_image_prompt = dalle_prompt_response.choices[0].message.content.strip()
        print(f"✨ Şəkil promptu:\n{final_image_prompt}\n")
    except FileNotFoundError:
        print("❌ systemarium_prompt.txt tapılmadı!")
        return
    except Exception as e:
        print(f"❌ OpenAI Xətası (Prompt): {e}")
        return

    # 3. Şəkil generasiyası
    print("🖼️ 3. Şəkil yaradılır...")
    local_img_name = None
    img_data = None
    try:
        image_response = client.images.generate(
            model=IMAGE_MODEL,
            prompt=final_image_prompt[:4000],
            size="1024x1024",
            n=1
            # response_format SİLİNDİ — gpt-image-1 həmişə b64_json qaytarır
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
- 1-ci: hook (diqqətçəkən sual/cümlə)
- 2-ci: qısa izah
- 3-cü: call-to-action
- Maksimum 50-70 söz, 3-4 emoji
- Sonda 5 populyar hashtag
- Qrammatik düzgün Azərbaycan dili"""

    try:
        caption_response = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": caption_prompt}]
        )
        caption = caption_response.choices[0].message.content.strip()
        print(f"📜 Caption:\n{caption}\n")
    except Exception as e:
        print(f"❌ OpenAI Xətası (Caption): {e}")
        cleanup(local_img_name)
        return

    # 5. İnstagram + GitHub sessiya
    print("📱 5. İnstagram-a bağlanır...")
    cl = Client()
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)

    session_existed = False
    try:
        try:
            session_file = repo.get_contents("session.json")
            with open("session.json", "wb") as f:
                f.write(session_file.decoded_content)
            cl.load_settings("session.json")
            cl.login(IG_USERNAME, IG_PASSWORD)
            session_existed = True
            print("✅ Mövcud sessiya yükləndi.")
        except GithubException:
            cl.login(IG_USERNAME, IG_PASSWORD)
            cl.dump_settings("session.json")
            with open("session.json", "r") as f:
                session_data = f.read()
            repo.create_file("session.json", "Save IG session", session_data)
            print("✅ Yeni sessiya yaradıldı və GitHub-a saxlandı.")

        print("✅ Paylaşılır...")
        cl.photo_upload(local_img_name, caption)
        print("🎉 POST PAYLAŞILDI!")

        # Sessiyanı yenilə (əgər mövcud idisə update et)
        if session_existed:
            try:
                cl.dump_settings("session.json")
                with open("session.json", "r") as f:
                    new_session = f.read()
                contents = repo.get_contents("session.json")
                repo.update_file("session.json", "Update IG session", new_session, contents.sha)
            except Exception as e:
                print(f"⚠️ Sessiya yenilənmədi: {e}")

    except Exception as e:
        print(f"❌ İnstagram xətası: {e}")
        cleanup(local_img_name)
        return

    # 6. Şəkli arxivləmək
    print("🔄 6. Şəkil GitHub arxivinə yüklənir...")
    try:
        repo.create_file(f"images/{local_img_name}", f"Avtomatik post: {post_idea}", img_data)
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
