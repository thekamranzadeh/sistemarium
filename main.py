import os
import base64
from datetime import datetime
from github import Github
from github.GithubException import GithubException
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

# --- MODELLƏR ---
TEXT_MODEL = "gpt-5.5-2026-04-23"     # ideya və caption üçün
SMART_MODEL = "gpt-5.5-2026-04-23"    # şəkil promptu üçün
IMAGE_MODEL = "gpt-image-1"           # şəkil generasiyası

# --- MÖVZUNUZ ---
PAGE_TOPIC = "AI və onun insan psixologiyasına təsiri haqqında növbəti 10 il üçün nələr baş verəcəyi ilə bağlı düşüncələr."


def main():
    print("🚀 TAM AVTOMATİK İnstagram Botu işə düşdü...")

    if not all([IG_USERNAME, IG_PASSWORD, OPENAI_API_KEY, GITHUB_TOKEN, GITHUB_REPO]):
        print("❌ .env faylında məlumatlar əksikdir!")
        return

    client = OpenAI(api_key=OPENAI_API_KEY)

    # 1. Mövzu İdeyası
    print("🧠 1. Yeni post üçün mövzu ideyası düşünülür...")
    try:
        idea_response = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{
                "role": "user",
                "content": f"Sən '{PAGE_TOPIC}' mövzusunda İnstagram səhifəsi işlədirsən. Mənə elə indicə paylaşmaq üçün maraqlı, diqqətçəkən, tək bir cümləlik İDEYA (mövzu başlığı) ver. Sual vermə, yalnız ideyanı yaz."
            }],
            reasoning_effort="low"
        )
        post_idea = idea_response.choices[0].message.content.strip()
        print(f"💡 İdeya tapıldı: {post_idea}")
    except Exception as e:
        print(f"❌ OpenAI Xətası (İdeya): {e}")
        return

    # 2. Şəkil üçün Prompt
    print("🎨 2. Meta-Prompt əsasında unikal şəkil promptu hazırlanır...")
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
        print(f"✨ Şəkil üçün göndərilən əmr:\n{final_image_prompt}\n")
    except FileNotFoundError:
        print("❌ systemarium_prompt.txt faylı tapılmadı!")
        return
    except Exception as e:
        print(f"❌ OpenAI Xətası (Prompt Generasiyası): {e}")
        return

    # 3. Şəkil Yaratmaq
    print("🖼️ 3. Şəkil çəkilir (Bu 10-15 saniyə çəkə bilər)...")
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

        print(f"🖼️ Şəkil generasiya edildi: {local_img_name}")
    except Exception as e:
        print(f"❌ Şəkil yaradılarkən xəta: {e}")
        return

    # 4. Caption (Mətn)
    print("📝 4. Şəkilə uyğun Caption yazılır...")
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
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": caption_prompt}],
            reasoning_effort="low"
        )
        caption = caption_response.choices[0].message.content.strip()
        print(f"📜 Hazır Mətn:\n{caption}\n")
    except Exception as e:
        print(f"❌ OpenAI Xətası (Caption): {e}")
        cleanup(local_img_name)
        return

    # 5. İnstagram-a Bağlanmaq
    print("📱 5. İnstagram-a bağlanır...")
    cl = Client()
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)

    session_existed = False
    try:
        # Sessiyanı GitHub-dan yükləməyə çalışırıq
        try:
            session_file = repo.get_contents("session.json")
            with open("session.json", "wb") as f:
                f.write(session_file.decoded_content)
            cl.load_settings("session.json")
            cl.login(IG_USERNAME, IG_PASSWORD)
            session_existed = True
            print("✅ Mövcud sessiya yükləndi (Təhlükəsiz giriş).")
        except GithubException:
            # Sessiya yoxdursa, sıfırdan giriş
            cl.login(IG_USERNAME, IG_PASSWORD)
            cl.dump_settings("session.json")
            with open("session.json", "r") as f:
                session_data = f.read()
            repo.create_file("session.json", "Save IG session", session_data)
            print("✅ Yeni sessiya yaradıldı və GitHub-a saxlanıldı.")

        print("✅ Hesaba daxil olundu. Paylaşılır...")
        cl.photo_upload(local_img_name, caption)
        print("🎉 POST İNSTAGRAMDA UĞURLA PAYLAŞILDI!")

        # Sessiyanı yeniləmək (varsa update)
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

    except Exception as e:
        print(f"❌ İnstagram Xətası: {e}")
        cleanup(local_img_name)
        return

    # 6. Şəkli GitHub-da Arxivləmək
    print("🔄 6. Şəkil GitHub arxivinə yüklənir...")
    try:
        repo.create_file(f"images/{local_img_name}", f"Avtomatik post: {post_idea}", img_data)
        print("✅ Şəkil GitHub-da arxivləşdirildi.")
    except Exception as e:
        print(f"⚠️ GitHub-a yükləmədə problem (amma post paylaşıldı): {e}")

    # Təmizlik
    cleanup(local_img_name)
    print("🚀 BÜTÜN PROSES QÜSURSUZ TAMAMLANDI! Növbəti post 1 saat sonra olacaq.")


def cleanup(img_name):
    if img_name and os.path.exists(img_name):
        os.remove(img_name)
    if os.path.exists("session.json"):
        os.remove("session.json")


if __name__ == "__main__":
    main()
