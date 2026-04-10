"""
Generate a sample iap_data.xlsx file for testing.

Run: python generate_sample_data.py
"""

import pandas as pd
from pathlib import Path

SAMPLE_DATA = [
    {
        "product_id": "com.studio.game.gem_pack_1",
        "iap_type": "consumable",
        "base_price_usd": 0.99,
        "name_en": "Gem Pack – Small",
        "desc_en": "A small pack of 100 gems to boost your progress.",
        "name_vi": "Gói Kim Cương – Nhỏ",
        "desc_vi": "Gói nhỏ gồm 100 kim cương để tăng tốc tiến trình.",
    },
    {
        "product_id": "com.studio.game.gem_pack_2",
        "iap_type": "consumable",
        "base_price_usd": 4.99,
        "name_en": "Gem Pack – Medium",
        "desc_en": "A medium pack of 600 gems. Best value for casual players!",
        "name_vi": "Gói Kim Cương – Vừa",
        "desc_vi": "Gói vừa gồm 600 kim cương. Giá trị tốt nhất cho game thủ!",
    },
    {
        "product_id": "com.studio.game.gem_pack_3",
        "iap_type": "consumable",
        "base_price_usd": 9.99,
        "name_en": "Gem Pack – Large",
        "desc_en": "A large pack of 1500 gems. The ultimate power-up!",
        "name_vi": "Gói Kim Cương – Lớn",
        "desc_vi": "Gói lớn gồm 1500 kim cương. Sức mạnh tối thượng!",
    },
    {
        "product_id": "com.studio.game.gem_pack_mega",
        "iap_type": "consumable",
        "base_price_usd": 19.99,
        "name_en": "Gem Pack – Mega",
        "desc_en": "A mega pack of 4000 gems. Dominate the leaderboard!",
        "name_vi": "Gói Kim Cương – Siêu Lớn",
        "desc_vi": "Gói siêu lớn gồm 4000 kim cương. Thống trị bảng xếp hạng!",
    },
    {
        "product_id": "com.studio.game.coin_pack_1",
        "iap_type": "consumable",
        "base_price_usd": 1.99,
        "name_en": "Coin Bundle – Starter",
        "desc_en": "500 coins to get you started.",
        "name_vi": "Gói Xu – Khởi Đầu",
        "desc_vi": "500 xu để bắt đầu hành trình.",
    },
    {
        "product_id": "com.studio.game.coin_pack_2",
        "iap_type": "consumable",
        "base_price_usd": 4.99,
        "name_en": "Coin Bundle – Pro",
        "desc_en": "2000 coins for the serious gamer.",
        "name_vi": "Gói Xu – Pro",
        "desc_vi": "2000 xu cho game thủ chuyên nghiệp.",
    },
    {
        "product_id": "com.studio.game.no_ads",
        "iap_type": "non-consumable",
        "base_price_usd": 2.99,
        "name_en": "Remove Ads",
        "desc_en": "Permanently remove all advertisements from the game.",
        "name_vi": "Xóa Quảng Cáo",
        "desc_vi": "Xóa vĩnh viễn tất cả quảng cáo trong trò chơi.",
    },
    {
        "product_id": "com.studio.game.premium_unlock",
        "iap_type": "non-consumable",
        "base_price_usd": 5.99,
        "name_en": "Premium Unlock",
        "desc_en": "Unlock all premium levels and exclusive content.",
        "name_vi": "Mở Khóa Premium",
        "desc_vi": "Mở khóa tất cả màn chơi premium và nội dung độc quyền.",
    },
    {
        "product_id": "com.studio.game.vip_pass",
        "iap_type": "non-consumable",
        "base_price_usd": 9.99,
        "name_en": "VIP Pass",
        "desc_en": "Get VIP status with exclusive rewards and double XP.",
        "name_vi": "Thẻ VIP",
        "desc_vi": "Nhận trạng thái VIP với phần thưởng độc quyền và nhân đôi XP.",
    },
    {
        "product_id": "com.studio.game.starter_bundle",
        "iap_type": "non-consumable",
        "base_price_usd": 3.99,
        "name_en": "Starter Bundle",
        "desc_en": "Everything you need to jumpstart your adventure!",
        "name_vi": "Gói Khởi Đầu",
        "desc_vi": "Tất cả những gì bạn cần để bắt đầu cuộc phiêu lưu!",
    },
]


def main() -> None:
    df = pd.DataFrame(SAMPLE_DATA)
    output = Path("iap_data.xlsx")
    df.to_excel(output, index=False, engine="openpyxl")
    print(f"[OK] Sample data written to: {output.resolve()}")
    print(f"   -> {len(df)} products ({df['iap_type'].value_counts().to_dict()})")


if __name__ == "__main__":
    main()
