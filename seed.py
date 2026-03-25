"""
数据初始化脚本
创建地点和种子留言数据
"""
import random
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import SYNC_DATABASE_URL, sync_engine
from models import Base, Location, Message, init_models


# 昵称生成词库
ADJECTIVES = [
    "安静的", "快乐的", "迷路的", "认真的", "困困的", "饥饿的", "好奇的", "勇敢的",
    "害羞的", "暴躁的", "优雅的", "沉默的", "活泼的", "懒散的", "机智的", "温柔的",
    "神秘的", "倔强的", "疲惫的", "淡定的"
]

ANIMALS = [
    "海豹", "熊猫", "柴犬", "猫头鹰", "企鹅", "水獭", "仓鼠", "考拉", "狐狸", "刺猬",
    "兔子", "鹦鹉", "海龟", "松鼠", "浣熊", "树懒", "白鲸", "柯基", "河马", "火烈鸟"
]


def generate_nickname():
    """生成随机昵称"""
    return random.choice(ADJECTIVES) + random.choice(ANIMALS)


# 地点数据
LOCATIONS = [
    {"id": "library-main", "name": "图书馆", "description": "知识的海洋，卷王的战场"},
    {"id": "east9", "name": "东九教学楼", "description": "上课、自习、发呆的地方"},
    {"id": "canteen-baiwei", "name": "百味食堂", "description": "今天吃什么是永恒的难题"},
    {"id": "gym", "name": "光谷体育馆", "description": "挥洒汗水的地方"},
    {"id": "dorm-south", "name": "南边宿舍区", "description": "回到温暖的小窝"},
]

# 种子留言数据
SEED_MESSAGES = {
    "library-main": [
        "三楼西区今天人好少，赚到了",
        "四楼靠窗那排插座最多",
        "闭馆音乐响起的时候，才发现外面天都黑了",
        "今天终于抢到了靠窗的位置",
    ],
    "east9": [
        "这个教室的空调永远是个谜",
        "下午三点的阳光正好，适合发呆",
        "有没有人知道A101的门怎么老是锁着",
        "期中考试周，这里变成了战场",
    ],
    "canteen-baiwei": [
        "二楼新来的麻辣香锅可以的",
        "中午12点来排队简直是自虐",
        "推荐一楼的煲仔饭，分量足",
        "今天的糖醋排骨居然没抢完",
    ],
    "gym": [
        "有没有人周末打羽毛球",
        "游泳馆的水温刚刚好",
        "健身房人太多了，还是跑步机最香",
        "篮球场今天居然空着",
    ],
    "dorm-south": [
        "又到了纠结洗不洗澡的时间",
        "楼下那只猫又在蹭吃蹭喝",
        "今晚外卖点什么好呢",
        "室友的呼噜声简直是白噪音",
    ],
}


def main():
    """初始化数据库和种子数据"""
    print("正在初始化数据库...")

    # 创建表
    Base.metadata.create_all(sync_engine)
    print("数据库表创建完成")

    # 创建会话
    Session = sessionmaker(bind=sync_engine)
    session = Session()

    try:
        # 检查是否已有数据
        existing_count = session.query(Location).count()
        if existing_count > 0:
            print(f"数据库已有 {existing_count} 个地点，跳过初始化")
            return

        # 创建地点
        for loc_data in LOCATIONS:
            location = Location(
                id=loc_data["id"],
                name=loc_data["name"],
                description=loc_data["description"],
                scan_count=random.randint(10, 100),  # 随机初始扫码次数
                created_at=datetime.utcnow()
            )
            session.add(location)
            print(f"创建地点: {location.name}")

        session.commit()

        # 创建种子留言
        for loc_id, messages in SEED_MESSAGES.items():
            for content in messages:
                message = Message(
                    location_id=loc_id,
                    content=content,
                    nickname=generate_nickname(),
                    session_id=f"seed-{random.randint(1000, 9999)}",
                    created_at=datetime.utcnow()
                )
                session.add(message)

        session.commit()
        print(f"创建了 {sum(len(msgs) for msgs in SEED_MESSAGES.values())} 条种子留言")

        print("\n初始化完成！")
        print("运行 'uvicorn main:app --reload' 启动服务")

    except Exception as e:
        session.rollback()
        print(f"初始化失败: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
