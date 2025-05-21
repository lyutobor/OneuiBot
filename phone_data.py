# phone_data.py

PHONE_COLORS = ["Черный", "Красный", "Синий", "Желтый", "Белый"]

PHONE_MODELS = [
    # --- S Series ---
    {"key": "galaxy_s1", "name": "Samsung Galaxy S1", "series": "S", "display_name": "Galaxy S1", "memory": "8GB", "price": 500, "release_year": 2010}, # Память уточнена для примера
    {"key": "galaxy_s2", "name": "Samsung Galaxy S2", "series": "S", "display_name": "Galaxy S2", "memory": "16GB", "price": 600, "release_year": 2011}, # Память уточнена
    {"key": "galaxy_s3_16gb", "name": "Samsung Galaxy S3 16GB", "series": "S", "display_name": "Galaxy S3", "memory": "16GB", "price": 650, "release_year": 2012},
    {"key": "galaxy_s4_16gb", "name": "Samsung Galaxy S4 16GB", "series": "S", "display_name": "Galaxy S4", "memory": "16GB", "price": 700, "release_year": 2013},
    {"key": "galaxy_s5_16gb", "name": "Samsung Galaxy S5 16GB", "series": "S", "display_name": "Galaxy S5", "memory": "16GB", "price": 699, "release_year": 2014},

    {"key": "galaxy_s6_32gb", "name": "Samsung Galaxy S6 32GB", "series": "S", "display_name": "Galaxy S6", "memory": "32GB", "price": 720, "release_year": 2015},
    {"key": "galaxy_s6_edge_32gb", "name": "Samsung Galaxy S6 Edge 32GB", "series": "S", "display_name": "Galaxy S6 Edge", "memory": "32GB", "price": 820, "release_year": 2015},
    {"key": "galaxy_s6_edge_64gb", "name": "Samsung Galaxy S6 Edge 64GB", "series": "S", "display_name": "Galaxy S6 Edge", "memory": "64GB", "price": 900, "release_year": 2015}, # Доп. цена
    {"key": "galaxy_s6_edge_plus_32gb", "name": "Samsung Galaxy S6 Edge+ 32GB", "series": "S", "display_name": "Galaxy S6 Edge+", "memory": "32GB", "price": 870, "release_year": 2015}, # Уточнена память

    {"key": "galaxy_s7_32gb", "name": "Samsung Galaxy S7 32GB", "series": "S", "display_name": "Galaxy S7", "memory": "32GB", "price": 750, "release_year": 2016},
    {"key": "galaxy_s7_64gb", "name": "Samsung Galaxy S7 64GB", "series": "S", "display_name": "Galaxy S7", "memory": "64GB", "price": 830, "release_year": 2016}, # Доп. цена
    {"key": "galaxy_s7_edge_32gb", "name": "Samsung Galaxy S7 Edge 32GB", "series": "S", "display_name": "Galaxy S7 Edge", "memory": "32GB", "price": 850, "release_year": 2016},
    {"key": "galaxy_s7_edge_64gb", "name": "Samsung Galaxy S7 Edge 64GB", "series": "S", "display_name": "Galaxy S7 Edge", "memory": "64GB", "price": 930, "release_year": 2016}, # Доп. цена

    {"key": "galaxy_s8_64gb", "name": "Samsung Galaxy S8 64GB", "series": "S", "display_name": "Galaxy S8", "memory": "64GB", "price": 850, "release_year": 2017},
    {"key": "galaxy_s8_plus_64gb", "name": "Samsung Galaxy S8+ 64GB", "series": "S", "display_name": "Galaxy S8+", "memory": "64GB", "price": 950, "release_year": 2017},

    {"key": "galaxy_s9_64gb", "name": "Samsung Galaxy S9 64GB", "series": "S", "display_name": "Galaxy S9", "memory": "64GB", "price": 899, "release_year": 2018},
    {"key": "galaxy_s9_128gb", "name": "Samsung Galaxy S9 128GB", "series": "S", "display_name": "Galaxy S9", "memory": "128GB", "price": 999, "release_year": 2018}, # Доп. цена
    {"key": "galaxy_s9_256gb", "name": "Samsung Galaxy S9 256GB", "series": "S", "display_name": "Galaxy S9", "memory": "256GB", "price": 1099, "release_year": 2018},# Доп. цена
    {"key": "galaxy_s9_plus_64gb", "name": "Samsung Galaxy S9+ 64GB", "series": "S", "display_name": "Galaxy S9+", "memory": "64GB", "price": 999, "release_year": 2018},
    {"key": "galaxy_s9_plus_128gb", "name": "Samsung Galaxy S9+ 128GB", "series": "S", "display_name": "Galaxy S9+", "memory": "128GB", "price": 1099, "release_year": 2018},# Доп. цена
    {"key": "galaxy_s9_plus_256gb", "name": "Samsung Galaxy S9+ 256GB", "series": "S", "display_name": "Galaxy S9+", "memory": "256GB", "price": 1199, "release_year": 2018},# Доп. цена

    {"key": "galaxy_s10e_128gb", "name": "Samsung Galaxy S10e 128GB", "series": "S", "display_name": "Galaxy S10e", "memory": "128GB", "price": 799, "release_year": 2019},
    {"key": "galaxy_s10_128gb", "name": "Samsung Galaxy S10 128GB", "series": "S", "display_name": "Galaxy S10", "memory": "128GB", "price": 899, "release_year": 2019},
    {"key": "galaxy_s10_512gb", "name": "Samsung Galaxy S10 512GB", "series": "S", "display_name": "Galaxy S10", "memory": "512GB", "price": 1049, "release_year": 2019},# Доп. цена
    {"key": "galaxy_s10_plus_128gb", "name": "Samsung Galaxy S10+ 128GB", "series": "S", "display_name": "Galaxy S10+", "memory": "128GB", "price": 999, "release_year": 2019},
    {"key": "galaxy_s10_plus_512gb", "name": "Samsung Galaxy S10+ 512GB", "series": "S", "display_name": "Galaxy S10+", "memory": "512GB", "price": 1149, "release_year": 2019}, # Доп. цена
    {"key": "galaxy_s10_plus_1tb", "name": "Samsung Galaxy S10+ 1TB", "series": "S", "display_name": "Galaxy S10+", "memory": "1TB", "price": 1349, "release_year": 2019},    # Доп. цена
    {"key": "galaxy_s10_5g_256gb", "name": "Samsung Galaxy S10 5G 256GB", "series": "S", "display_name": "Galaxy S10 5G", "memory": "256GB", "price": 1149, "release_year": 2019},

    {"key": "galaxy_s20_128gb", "name": "Samsung Galaxy S20 128GB", "series": "S", "display_name": "Galaxy S20", "memory": "128GB", "price": 899, "release_year": 2020},
    {"key": "galaxy_s20_plus_128gb", "name": "Samsung Galaxy S20+ 128GB", "series": "S", "display_name": "Galaxy S20+", "memory": "128GB", "price": 999, "release_year": 2020},
    {"key": "galaxy_s20_ultra_128gb", "name": "Samsung Galaxy S20 Ultra 128GB", "series": "S", "display_name": "Galaxy S20 Ultra", "memory": "128GB", "price": 1199, "release_year": 2020},
    {"key": "galaxy_s20_fe_128gb", "name": "Samsung Galaxy S20 FE 128GB", "series": "S", "display_name": "Galaxy S20 FE", "memory": "128GB", "price": 759, "release_year": 2020},

    {"key": "galaxy_s21_128gb", "name": "Samsung Galaxy S21 128GB", "series": "S", "display_name": "Galaxy S21", "memory": "128GB", "price": 859, "release_year": 2021},
    {"key": "galaxy_s21_plus_128gb", "name": "Samsung Galaxy S21+ 128GB", "series": "S", "display_name": "Galaxy S21+", "memory": "128GB", "price": 969, "release_year": 2021},
    {"key": "galaxy_s21_plus_256gb", "name": "Samsung Galaxy S21+ 256GB", "series": "S", "display_name": "Galaxy S21+", "memory": "256GB", "price": 1069, "release_year": 2021},# Доп. цена
    {"key": "galaxy_s21_ultra_128gb", "name": "Samsung Galaxy S21 Ultra 128GB", "series": "S", "display_name": "Galaxy S21 Ultra", "memory": "128GB", "price": 1169, "release_year": 2021},
    {"key": "galaxy_s21_ultra_256gb", "name": "Samsung Galaxy S21 Ultra 256GB", "series": "S", "display_name": "Galaxy S21 Ultra", "memory": "256GB", "price": 1289, "release_year": 2021},# Доп. цена
    {"key": "galaxy_s21_ultra_512gb", "name": "Samsung Galaxy S21 Ultra 512GB", "series": "S", "display_name": "Galaxy S21 Ultra", "memory": "512GB", "price": 1439, "release_year": 2021},# Доп. цена
    {"key": "galaxy_s21_fe_128gb", "name": "Samsung Galaxy S21 FE 128GB", "series": "S", "display_name": "Galaxy S21 FE", "memory": "128GB", "price": 799, "release_year": 2022},
    {"key": "galaxy_s21_fe_256gb", "name": "Samsung Galaxy S21 FE 256GB", "series": "S", "display_name": "Galaxy S21 FE", "memory": "256GB", "price": 899, "release_year": 2022}, # Доп. цена

    {"key": "galaxy_s22_128gb", "name": "Samsung Galaxy S22 128GB", "series": "S", "display_name": "Galaxy S22", "memory": "128GB", "price": 859, "release_year": 2022},
    {"key": "galaxy_s22_256gb", "name": "Samsung Galaxy S22 256GB", "series": "S", "display_name": "Galaxy S22", "memory": "256GB", "price": 959, "release_year": 2022},   # Доп. цена
    {"key": "galaxy_s22_plus_128gb", "name": "Samsung Galaxy S22+ 128GB", "series": "S", "display_name": "Galaxy S22+", "memory": "128GB", "price": 969, "release_year": 2022},
    {"key": "galaxy_s22_plus_256gb", "name": "Samsung Galaxy S22+ 256GB", "series": "S", "display_name": "Galaxy S22+", "memory": "256GB", "price": 1069, "release_year": 2022}, # Доп. цена
    {"key": "galaxy_s22_ultra_128gb", "name": "Samsung Galaxy S22 Ultra 128GB", "series": "S", "display_name": "Galaxy S22 Ultra", "memory": "128GB", "price": 1169, "release_year": 2022},
    {"key": "galaxy_s22_ultra_256gb", "name": "Samsung Galaxy S22 Ultra 256GB", "series": "S", "display_name": "Galaxy S22 Ultra", "memory": "256GB", "price": 1289, "release_year": 2022},# Доп. цена
    {"key": "galaxy_s22_ultra_512gb", "name": "Samsung Galaxy S22 Ultra 512GB", "series": "S", "display_name": "Galaxy S22 Ultra", "memory": "512GB", "price": 1439, "release_year": 2022},# Доп. цена

    {"key": "galaxy_s23_128gb", "name": "Samsung Galaxy S23 128GB", "series": "S", "display_name": "Galaxy S23", "memory": "128GB", "price": 859, "release_year": 2023},
    {"key": "galaxy_s23_256gb", "name": "Samsung Galaxy S23 256GB", "series": "S", "display_name": "Galaxy S23", "memory": "256GB", "price": 959, "release_year": 2023},   # Доп. цена
    {"key": "galaxy_s23_plus_256gb", "name": "Samsung Galaxy S23+ 256GB", "series": "S", "display_name": "Galaxy S23+", "memory": "256GB", "price": 969, "release_year": 2023},
    {"key": "galaxy_s23_plus_512gb", "name": "Samsung Galaxy S23+ 512GB", "series": "S", "display_name": "Galaxy S23+", "memory": "512GB", "price": 1119, "release_year": 2023},# Доп. цена
    {"key": "galaxy_s23_ultra_256gb", "name": "Samsung Galaxy S23 Ultra 256GB", "series": "S", "display_name": "Galaxy S23 Ultra", "memory": "256GB", "price": 1219, "release_year": 2023},
    {"key": "galaxy_s23_ultra_512gb", "name": "Samsung Galaxy S23 Ultra 512GB", "series": "S", "display_name": "Galaxy S23 Ultra", "memory": "512GB", "price": 1369, "release_year": 2023},# Доп. цена
    {"key": "galaxy_s23_ultra_1tb", "name": "Samsung Galaxy S23 Ultra 1TB", "series": "S", "display_name": "Galaxy S23 Ultra", "memory": "1TB", "price": 1569, "release_year": 2023},  # Доп. цена
    {"key": "galaxy_s23_fe_128gb", "name": "Samsung Galaxy S23 FE 128GB", "series": "S", "display_name": "Galaxy S23 FE", "memory": "128GB", "price": 749, "release_year": 2023},
    {"key": "galaxy_s23_fe_256gb", "name": "Samsung Galaxy S23 FE 256GB", "series": "S", "display_name": "Galaxy S23 FE", "memory": "256GB", "price": 849, "release_year": 2023},  # Доп. цена

    {"key": "galaxy_s24_128gb", "name": "Samsung Galaxy S24 128GB", "series": "S", "display_name": "Galaxy S24", "memory": "128GB", "price": 899, "release_year": 2024},
    {"key": "galaxy_s24_256gb", "name": "Samsung Galaxy S24 256GB", "series": "S", "display_name": "Galaxy S24", "memory": "256GB", "price": 999, "release_year": 2024},   # Доп. цена
    {"key": "galaxy_s24_plus_256gb", "name": "Samsung Galaxy S24+ 256GB", "series": "S", "display_name": "Galaxy S24+", "memory": "256GB", "price": 1049, "release_year": 2024},
    {"key": "galaxy_s24_plus_512gb", "name": "Samsung Galaxy S24+ 512GB", "series": "S", "display_name": "Galaxy S24+", "memory": "512GB", "price": 1199, "release_year": 2024},# Доп. цена
    {"key": "galaxy_s24_ultra_256gb", "name": "Samsung Galaxy S24 Ultra 256GB", "series": "S", "display_name": "Galaxy S24 Ultra", "memory": "256GB", "price": 1319, "release_year": 2024},
    {"key": "galaxy_s24_ultra_512gb", "name": "Samsung Galaxy S24 Ultra 512GB", "series": "S", "display_name": "Galaxy S24 Ultra", "memory": "512GB", "price": 1469, "release_year": 2024},# Доп. цена
    {"key": "galaxy_s24_ultra_1tb", "name": "Samsung Galaxy S24 Ultra 1TB", "series": "S", "display_name": "Galaxy S24 Ultra", "memory": "1TB", "price": 1669, "release_year": 2024},  # Доп. цена

    {"key": "galaxy_s25_256gb", "name": "Samsung Galaxy S25 256GB", "series": "S", "display_name": "Galaxy S25", "memory": "256GB", "price": 1359, "release_year": 2025},
    {"key": "galaxy_s25_512gb", "name": "Samsung Galaxy S25 512GB", "series": "S", "display_name": "Galaxy S25", "memory": "512GB", "price": 1509, "release_year": 2025},   # Доп. цена
    {"key": "galaxy_s25_plus_256gb", "name": "Samsung Galaxy S25+ 256GB", "series": "S", "display_name": "Galaxy S25+", "memory": "256GB", "price": 1500, "release_year": 2025},
    {"key": "galaxy_s25_plus_512gb", "name": "Samsung Galaxy S25+ 512GB", "series": "S", "display_name": "Galaxy S25+", "memory": "512GB", "price": 1650, "release_year": 2025},# Доп. цена
    {"key": "galaxy_s25_ultra_256gb", "name": "Samsung Galaxy S25 Ultra 256GB", "series": "S", "display_name": "Galaxy S25 Ultra", "memory": "256GB", "price": 1650, "release_year": 2025},
    {"key": "galaxy_s25_ultra_512gb", "name": "Samsung Galaxy S25 Ultra 512GB", "series": "S", "display_name": "Galaxy S25 Ultra", "memory": "512GB", "price": 1800, "release_year": 2025},# Доп. цена
    {"key": "galaxy_s25_ultra_1tb", "name": "Samsung Galaxy S25 Ultra 1TB", "series": "S", "display_name": "Galaxy S25 Ultra", "memory": "1TB", "price": 1999, "release_year": 2025}, # Доп. цена, ближе к верхней границе

    # --- A Series ---
    {"key": "galaxy_a01_16gb", "name": "Samsung Galaxy A01 16GB", "series": "A", "display_name": "Galaxy A01", "memory": "16GB", "price": 130, "release_year": 2019}, # Уточнена память
    {"key": "galaxy_a10_32gb", "name": "Samsung Galaxy A10 32GB", "series": "A", "display_name": "Galaxy A10", "memory": "32GB", "price": 199, "release_year": 2019},
    {"key": "galaxy_a11_32gb", "name": "Samsung Galaxy A11 32GB", "series": "A", "display_name": "Galaxy A11", "memory": "32GB", "price": 160, "release_year": 2020}, # Пример из диапазона
    {"key": "galaxy_a20_32gb", "name": "Samsung Galaxy A20 32GB", "series": "A", "display_name": "Galaxy A20", "memory": "32GB", "price": 229, "release_year": 2019},
    {"key": "galaxy_a20s_32gb", "name": "Samsung Galaxy A20s 32GB", "series": "A", "display_name": "Galaxy A20s", "memory": "32GB", "price": 249, "release_year": 2019},
    {"key": "galaxy_a21s_64gb", "name": "Samsung Galaxy A21s 64GB", "series": "A", "display_name": "Galaxy A21s", "memory": "64GB", "price": 200, "release_year": 2020}, # Пример
    {"key": "galaxy_a30_64gb", "name": "Samsung Galaxy A30 64GB", "series": "A", "display_name": "Galaxy A30", "memory": "64GB", "price": 279, "release_year": 2019},
    {"key": "galaxy_a30s_64gb", "name": "Samsung Galaxy A30s 64GB", "series": "A", "display_name": "Galaxy A30s", "memory": "64GB", "price": 299, "release_year": 2019},
    
    {"key": "galaxy_a50_64gb", "name": "Samsung Galaxy A50 64GB", "series": "A", "display_name": "Galaxy A50", "memory": "64GB", "price": 349, "release_year": 2019},
    {"key": "galaxy_a50_128gb", "name": "Samsung Galaxy A50 128GB", "series": "A", "display_name": "Galaxy A50", "memory": "128GB", "price": 399, "release_year": 2019}, # Доп. цена
    {"key": "galaxy_a51_128gb", "name": "Samsung Galaxy A51 128GB", "series": "A", "display_name": "Galaxy A51", "memory": "128GB", "price": 429, "release_year": 2020},
    {"key": "galaxy_a52_128gb", "name": "Samsung Galaxy A52 128GB", "series": "A", "display_name": "Galaxy A52", "memory": "128GB", "price": 429, "release_year": 2021},
    {"key": "galaxy_a52s_128gb", "name": "Samsung Galaxy A52s 128GB", "series": "A", "display_name": "Galaxy A52s", "memory": "128GB", "price": 499, "release_year": 2021},
    {"key": "galaxy_a53_128gb", "name": "Samsung Galaxy A53 128GB", "series": "A", "display_name": "Galaxy A53", "memory": "128GB", "price": 449, "release_year": 2022},
    {"key": "galaxy_a53_256gb", "name": "Samsung Galaxy A53 256GB", "series": "A", "display_name": "Galaxy A53", "memory": "256GB", "price": 529, "release_year": 2022}, # Доп. цена
    {"key": "galaxy_a54_128gb", "name": "Samsung Galaxy A54 128GB", "series": "A", "display_name": "Galaxy A54", "memory": "128GB", "price": 449, "release_year": 2023},
    {"key": "galaxy_a54_256gb", "name": "Samsung Galaxy A54 256GB", "series": "A", "display_name": "Galaxy A54", "memory": "256GB", "price": 529, "release_year": 2023}, # Доп. цена
    {"key": "galaxy_a55_128gb", "name": "Samsung Galaxy A55 128GB", "series": "A", "display_name": "Galaxy A55", "memory": "128GB", "price": 449, "release_year": 2024},
    {"key": "galaxy_a55_256gb", "name": "Samsung Galaxy A55 256GB", "series": "A", "display_name": "Galaxy A55", "memory": "256GB", "price": 529, "release_year": 2024}, # Доп. цена
    {"key": "galaxy_a56_128gb", "name": "Samsung Galaxy A56 128GB", "series": "A", "display_name": "Galaxy A56", "memory": "128GB", "price": 459, "release_year": 2025}, # Предположение
    {"key": "galaxy_a56_256gb", "name": "Samsung Galaxy A56 256GB", "series": "A", "display_name": "Galaxy A56", "memory": "256GB", "price": 539, "release_year": 2025}, # Предположение

    {"key": "galaxy_a70_128gb", "name": "Samsung Galaxy A70 128GB", "series": "A", "display_name": "Galaxy A70", "memory": "128GB", "price": 449, "release_year": 2019},
    {"key": "galaxy_a71_128gb", "name": "Samsung Galaxy A71 128GB", "series": "A", "display_name": "Galaxy A71", "memory": "128GB", "price": 529, "release_year": 2020},
    {"key": "galaxy_a72_128gb", "name": "Samsung Galaxy A72 128GB", "series": "A", "display_name": "Galaxy A72", "memory": "128GB", "price": 549, "release_year": 2021},
    {"key": "galaxy_a72_256gb", "name": "Samsung Galaxy A72 256GB", "series": "A", "display_name": "Galaxy A72", "memory": "256GB", "price": 629, "release_year": 2021}, # Доп. цена
    {"key": "galaxy_a73_128gb", "name": "Samsung Galaxy A73 128GB", "series": "A", "display_name": "Galaxy A73", "memory": "128GB", "price": 599, "release_year": 2022},
    {"key": "galaxy_a73_256gb", "name": "Samsung Galaxy A73 256GB", "series": "A", "display_name": "Galaxy A73", "memory": "256GB", "price": 679, "release_year": 2022}, # Доп. цена

    # --- Z Series ---
    {"key": "galaxy_z_flip_256gb", "name": "Samsung Galaxy Z Flip 256GB", "series": "Z", "display_name": "Galaxy Z Flip", "memory": "256GB", "price": 1570, "release_year": 2020},
    {"key": "galaxy_z_flip3_128gb", "name": "Samsung Galaxy Z Flip3 128GB", "series": "Z", "display_name": "Galaxy Z Flip3", "memory": "128GB", "price": 1420, "release_year": 2021},
    {"key": "galaxy_z_flip3_256gb", "name": "Samsung Galaxy Z Flip3 256GB", "series": "Z", "display_name": "Galaxy Z Flip3", "memory": "256GB", "price": 1520, "release_year": 2021},# Доп. цена
    {"key": "galaxy_z_flip4_128gb", "name": "Samsung Galaxy Z Flip4 128GB", "series": "Z", "display_name": "Galaxy Z Flip4", "memory": "128GB", "price": 1420, "release_year": 2022},
    {"key": "galaxy_z_flip4_256gb", "name": "Samsung Galaxy Z Flip4 256GB", "series": "Z", "display_name": "Galaxy Z Flip4", "memory": "256GB", "price": 1520, "release_year": 2022},# Доп. цена
    {"key": "galaxy_z_flip4_512gb", "name": "Samsung Galaxy Z Flip4 512GB", "series": "Z", "display_name": "Galaxy Z Flip4", "memory": "512GB", "price": 1670, "release_year": 2022},# Доп. цена
    {"key": "galaxy_z_flip5_256gb", "name": "Samsung Galaxy Z Flip5 256GB", "series": "Z", "display_name": "Galaxy Z Flip5", "memory": "256GB", "price": 1420, "release_year": 2023},
    {"key": "galaxy_z_flip5_512gb", "name": "Samsung Galaxy Z Flip5 512GB", "series": "Z", "display_name": "Galaxy Z Flip5", "memory": "512GB", "price": 1570, "release_year": 2023},# Доп. цена
    {"key": "galaxy_z_flip6_256gb", "name": "Samsung Galaxy Z Flip6 256GB", "series": "Z", "display_name": "Galaxy Z Flip6", "memory": "256GB", "price": 1470, "release_year": 2024},
    {"key": "galaxy_z_flip6_512gb", "name": "Samsung Galaxy Z Flip6 512GB", "series": "Z", "display_name": "Galaxy Z Flip6", "memory": "512GB", "price": 1620, "release_year": 2024},# Доп. цена

    {"key": "galaxy_fold_256gb", "name": "Samsung Galaxy Fold 256GB", "series": "Z", "display_name": "Galaxy Fold", "memory": "256GB", "price": 2000, "release_year": 2019}, # Память уточнена
    {"key": "galaxy_z_fold2_256gb", "name": "Samsung Galaxy Z Fold2 256GB", "series": "Z", "display_name": "Galaxy Z Fold2", "memory": "256GB", "price": 1980, "release_year": 2020},
    {"key": "galaxy_z_fold3_256gb", "name": "Samsung Galaxy Z Fold3 256GB", "series": "Z", "display_name": "Galaxy Z Fold3", "memory": "256GB", "price": 1799, "release_year": 2021},
    {"key": "galaxy_z_fold3_512gb", "name": "Samsung Galaxy Z Fold3 512GB", "series": "Z", "display_name": "Galaxy Z Fold3", "memory": "512GB", "price": 1949, "release_year": 2021},# Доп. цена
    {"key": "galaxy_z_fold4_256gb", "name": "Samsung Galaxy Z Fold4 256GB", "series": "Z", "display_name": "Galaxy Z Fold4", "memory": "256GB", "price": 1849, "release_year": 2022},
    {"key": "galaxy_z_fold4_512gb", "name": "Samsung Galaxy Z Fold4 512GB", "series": "Z", "display_name": "Galaxy Z Fold4", "memory": "512GB", "price": 1999, "release_year": 2022},# Доп. цена
    {"key": "galaxy_z_fold5_256gb", "name": "Samsung Galaxy Z Fold5 256GB", "series": "Z", "display_name": "Galaxy Z Fold5", "memory": "256GB", "price": 1849, "release_year": 2023},
    {"key": "galaxy_z_fold5_512gb", "name": "Samsung Galaxy Z Fold5 512GB", "series": "Z", "display_name": "Galaxy Z Fold5", "memory": "512GB", "price": 1999, "release_year": 2023},# Доп. цена
    {"key": "galaxy_z_fold6_256gb", "name": "Samsung Galaxy Z Fold6 256GB", "series": "Z", "display_name": "Galaxy Z Fold6", "memory": "256GB", "price": 1949, "release_year": 2024},
    {"key": "galaxy_z_fold6_512gb", "name": "Samsung Galaxy Z Fold6 512GB", "series": "Z", "display_name": "Galaxy Z Fold6", "memory": "512GB", "price": 2099, "release_year": 2024},# Доп. цена
]