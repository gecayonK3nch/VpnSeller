from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    BOT_TOKEN: str
    PAYMENT_TOKEN: str
    ADMIN_IDS: str
    DB_NAME: str = "vpn_bot.db"
    
    # VPN Config
    VPN_INTERFACE: str = "awg1"
    VPN_HOST: str
    VPN_PORT: int = 51821
    VPN_SUBNET: str = "10.9.0.0/24"
    VPN_DNS: str = "8.8.8.8"
    
    # Obfuscation
    AMNEZIA_JC: int
    AMNEZIA_JMIN: int
    AMNEZIA_JMAX: int
    AMNEZIA_S1: int
    AMNEZIA_S2: int
    AMNEZIA_H1: int
    AMNEZIA_H2: int
    AMNEZIA_H3: int
    AMNEZIA_H4: int

    # Prices (in RUB)
    PRICE_1_MONTH: int = 100
    PRICE_3_MONTHS: int = 400
    PRICE_12_MONTHS: int = 1500
    
    # Referral Settings
    REF_REWARD_THRESHOLD: int = 3
    REF_REWARD_DAYS: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        env_parse_none_str = "None"

    @property
    def admin_ids_list(self) -> List[int]:
        if isinstance(self.ADMIN_IDS, str):
            return [int(x.strip()) for x in self.ADMIN_IDS.split(',')]
        return self.ADMIN_IDS

settings = Settings()
