# Modern Discord AI Bot

## Fitur
- Slash command `/ai chat`
- Konteks percakapan singkat per pengguna dan channel
- Tombol **Balas** dan **Hapus riwayat**
- Sesi HTTP digunakan ulang, timeout, pembatasan concurrency, dan cooldown
- Respons panjang dipecah agar tidak melewati batas Discord
- Token Discord dan API key dibaca dari environment variable

## Instalasi
1. Gunakan Python 3.10 atau lebih baru.
2. Jalankan `pip install -r requirements.txt`.
3. Salin `.env.example` menjadi `.env`, lalu isi `DISCORD_TOKEN` dan `GROQ_API_KEY`.
4. Pasang `python-dotenv` sudah termasuk di requirements, lalu tambahkan dua baris berikut di bagian paling atas `bot.py` jika ingin membaca file `.env` otomatis:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```
5. Jalankan `python bot.py`.

Letakkan extension tambahan di folder `cogs/`. Contoh ini memakai `utils/colors.py`.

## Discord Developer Portal
Jika ingin memakai prefix command, aktifkan **Message Content Intent** pada halaman Bot di Discord Developer Portal. Slash command `/ai chat` tidak membutuhkan intent tersebut.

## Keamanan
Jangan simpan token Discord atau API key di source code, jangan commit file `.env`, dan jangan membagikan kredensial. Jika kredensial pernah terunggah atau terkirim ke orang lain, reset/revoke segera.
