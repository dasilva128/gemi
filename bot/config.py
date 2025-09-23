import yaml
import dotenv
from pathlib import Path

# مسیر دایرکتوری تنظیمات
config_dir = Path(__file__).parent.parent.resolve() / "config"

# بارگذاری فایل YAML
with open(config_dir / "config.yml", 'r') as f:
    config_yaml = yaml.safe_load(f)

# بارگذاری فایل .env
config_env = dotenv.dotenv_values(config_dir / "config.env")

# پارامترهای تنظیمات
telegram_token = config_yaml["telegram_token"]
gemini_api_key = config_yaml["gemini_api_key"]  # تغییر از openai_api_key به gemini_api_key
allowed_telegram_usernames = config_yaml.get("allowed_telegram_usernames", [])
new_dialog_timeout = config_yaml.get("new_dialog_timeout", 600)  # پیش‌فرض: 10 دقیقه
enable_message_streaming = config_yaml.get("enable_message_streaming", True)
n_chat_modes_per_page = config_yaml.get("n_chat_modes_per_page", 5)
mongodb_uri = f"mongodb://mongo:{config_env['MONGODB_PORT']}"

# حالت‌های چت
with open(config_dir / "chat_modes.yml", 'r') as f:
    chat_modes = yaml.safe_load(f)

# مدل‌ها
with open(config_dir / "models.yml", 'r') as f:
    models = yaml.safe_load(f)

# فایل‌های استاتیک
help_group_chat_video_path = Path(__file__).parent.parent.resolve() / "static" / "help_group.mp4"