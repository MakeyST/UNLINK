import os
import sys
from app import create_one_time_link

FILES = {
    "0": "Makey_HWID_LifeTime.rar",
    "1": "Makey_HWID_1_use.rar"
}


def main():
    if len(sys.argv) < 2:
        print("❌ Укажите аргумент: 0 или 1")
        sys.exit(1)

    choice = sys.argv[1].strip()

    if choice not in FILES:
        print("❌ Неверный выбор. Допустимо: 0 или 1")
        sys.exit(1)

    filename = FILES[choice]
    filepath = os.path.join('./uploads', filename)

    if not os.path.exists(filepath):
        print(f"❌ Файл '{filename}' не найден в папке ./uploads")
        sys.exit(1)

    link = create_one_time_link(filename)
    print("\n✅ Одноразовая ссылка создана:\n")
    print(link)


if __name__ == "__main__":
    main()
