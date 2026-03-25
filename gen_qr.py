"""
二维码生成脚本
为每个地点生成二维码图片
"""
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

from database import sync_engine
from models import Location
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


# 二维码基础 URL
BASE_URL = "https://weisuandi.com/loc/"

# 输出目录
OUTPUT_DIR = "qrcodes"


def generate_qrcode(location_id: str, location_name: str):
    """为指定地点生成二维码"""
    # 创建二维码
    url = f"{BASE_URL}{location_id}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # 生成二维码图片
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # 添加地点名称文字
    qr_width, qr_height = qr_img.size
    text_height = 40
    total_height = qr_height + text_height

    # 创建新图片（带文字区域）
    final_img = Image.new('RGB', (qr_width, total_height), 'white')
    final_img.paste(qr_img, (0, 0))

    # 添加文字
    draw = ImageDraw.Draw(final_img)

    # 尝试使用系统字体
    try:
        # Windows
        font = ImageFont.truetype("msyh.ttc", 16)  # 微软雅黑
    except:
        try:
            # macOS
            font = ImageFont.truetype("PingFang.ttc", 16)
        except:
            # 默认字体
            font = ImageFont.load_default()

    # 计算文字位置（居中）
    bbox = draw.textbbox((0, 0), location_name, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = (qr_width - text_width) // 2
    text_y = qr_height + 10

    draw.text((text_x, text_y), location_name, fill="black", font=font)

    return final_img


def main():
    """生成所有地点的二维码"""
    print("正在生成二维码...")

    # 创建输出目录
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 连接数据库
    Session = sessionmaker(bind=sync_engine)
    session = Session()

    try:
        # 查询所有地点
        locations = session.query(Location).all()

        if not locations:
            print("没有找到任何地点，请先运行 seed.py 初始化数据")
            return

        for loc in locations:
            # 生成二维码
            qr_img = generate_qrcode(loc.id, loc.name)

            # 保存文件
            output_path = os.path.join(OUTPUT_DIR, f"{loc.id}.png")
            qr_img.save(output_path)
            print(f"生成: {output_path} ({loc.name})")

        print(f"\n完成！共生成 {len(locations)} 个二维码")
        print(f"文件保存在 {OUTPUT_DIR}/ 目录下")

    except Exception as e:
        print(f"生成失败: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
