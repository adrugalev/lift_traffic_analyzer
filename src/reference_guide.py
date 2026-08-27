"""Пользовательские пояснения для инженерного справочника приложения."""

from __future__ import annotations

from html import escape

from src.models.building import BuildingType
from src.models.traffic import ArrivalDistribution


FORMULA_GROUPS = (
    (
        "Расчёт по ГОСТ 34758-2021",
        (
            "gost_nominal_speed",
            "gost_nominal_capacity",
            "gost_calculated_car_capacity",
            "gost_passenger_transfer_time",
            "gost_probable_stops",
            "gost_reversal_floor",
            "gost_adjacent_floor_time",
            "kinematic_acceleration_distance",
            "kinematic_maximum_speed",
            "gost_adjacent_floor_profile_time",
            "gost_stop_time",
            "gost_round_trip_time",
            "gost_interval",
            "gost_group_handling_capacity",
            "gost_handling_capacity_percent",
        ),
    ),
    (
        "Инженерный учёт паркинга (не формулы ГОСТ)",
        (
            "parking_lower_reversal",
            "parking_expected_depth",
            "parking_probable_stops",
            "parking_round_trip_extension",
        ),
    ),
    (
        "Предварительный расчёт и симуляция",
        (
            "calculated_car_capacity",
            "probable_stops_uniform",
            "highest_reversal_uniform",
            "motion_time",
            "engineering_cycle_time",
            "interval",
            "handling_capacity_5min",
            "average_wait_proxy",
        ),
    ),
)

# Порядок обозначений в пользовательской таблице под формулой.
# Включает результат, исходные величины и индексы суммирования, чтобы каждое
# обозначение из формулы было расшифровано рядом с ней.
FORMULA_VARIABLES_IN_ORDER = {
    "calculated_car_capacity": ("C", "Cном", "kзап"),
    "probable_stops_uniform": ("S", "N", "C"),
    "highest_reversal_uniform": ("H", "N", "C", "k"),
    "motion_time": ("tдв", "d", "v", "a", "b", "tразг", "tуст", "tторм"),
    "engineering_cycle_time": (
        "Tцикл",
        "tдв",
        "S",
        "tост",
        "C",
        "tпос",
        "tвыс",
    ),
    "interval": ("I", "Tцикл", "L"),
    "handling_capacity_5min": ("HC5", "C", "I"),
    "average_wait_proxy": ("tож,ор", "I"),
    "gost_nominal_speed": ("vн", "Hmax", "tн"),
    "gost_nominal_capacity": ("Pном", "Q"),
    "gost_calculated_car_capacity": ("Pк", "Pном", "kз"),
    "gost_passenger_transfer_time": ("tв", "bдвери"),
    "gost_probable_stops": ("S", "Nэт", "Pк"),
    "gost_reversal_floor": ("Nр", "Nэт", "Pк", "i"),
    "gost_adjacent_floor_time": ("tэт.н", "hэт", "vн"),
    "kinematic_acceleration_distance": ("sвм", "vм", "a", "j", "dф"),
    "kinematic_maximum_speed": ("vм", "a", "j", "dф"),
    "gost_adjacent_floor_profile_time": (
        "tэт",
        "hэт",
        "vн",
        "a",
        "b",
        "j",
        "tразг",
        "tуст",
        "tторм",
    ),
    "gost_stop_time": (
        "tост",
        "tз",
        "tз.д",
        "tэт",
        "tпр",
        "tо",
        "tз.з",
        "tэт.н",
    ),
    "gost_round_trip_time": ("T", "Nр", "tэт.н", "S", "tост", "Pк", "tв"),
    "gost_interval": ("tи", "T", "Nл"),
    "gost_group_handling_capacity": ("P5", "Pк", "Nл", "T", "tи"),
    "gost_handling_capacity_percent": ("%P5", "P5", "A"),
    "parking_lower_reversal": ("Hм", "M", "Pк", "qм", "k"),
    "parking_expected_depth": ("Dм", "Δhк", "M", "Pк", "qм", "k"),
    "parking_probable_stops": ("Sм", "M", "Pк", "qм"),
    "parking_round_trip_extension": (
        "Tм", "TГОСТ", "Dм", "vн", "Sм", "tост.м"
    ),
}


def formula_symbol_html(symbol: str) -> str:
    """Форматирует обозначение с математическим подстрочным индексом."""

    prefix = ""
    body = symbol
    if body.startswith("%"):
        prefix = "%"
        body = body[1:]

    base_length = 2 if body.startswith("HC") else 1
    base = escape(body[:base_length])
    index = escape(body[base_length:])
    prefix_html = escape(prefix)
    index_html = f"<sub>{index}</sub>" if index else ""
    return (
        '<span class="formula-symbol">'
        f"{prefix_html}<i>{base}</i>{index_html}"
        "</span>"
    )


FORMULA_LATEX = {
    "calculated_car_capacity": (
        r"C=\min\left(C_{\mathrm{ном}},"
        r"\operatorname{окр}_{0{,}5\uparrow}"
        r"(C_{\mathrm{ном}}k_{\mathrm{зап}})\right)"
    ),
    "probable_stops_uniform": (
        r"S=N\left[1-\left(\frac{N-1}{N}\right)^C\right]"
    ),
    "highest_reversal_uniform": (
        r"H=\sum_{k=1}^{N}\left[1-\left(\frac{k-1}{N}\right)^C\right]"
    ),
    "motion_time": (
        r"t_{\mathrm{дв}}=f(d,v,a,b)"
        r"=t_{\mathrm{разг}}+t_{\mathrm{уст}}+t_{\mathrm{торм}}"
    ),
    "engineering_cycle_time": (
        r"T_{\mathrm{цикл}}=2t_{\mathrm{дв}}+St_{\mathrm{ост}}"
        r"+C(t_{\mathrm{пос}}+t_{\mathrm{выс}})"
    ),
    "interval": r"I=\frac{T_{\mathrm{цикл}}}{L}",
    "handling_capacity_5min": r"HC_5=\frac{300C}{I}",
    "average_wait_proxy": r"t_{\mathrm{ож,ор}}\approx\frac{I}{2}",
    "gost_nominal_speed": r"v_{\mathrm{н}}=\frac{H_{\max}}{t_{\mathrm{н}}}",
    "gost_nominal_capacity": (
        r"P_{\mathrm{ном}}=\operatorname{окр}_{0{,}5\uparrow}"
        r"\left(\frac{Q}{75}\right)"
    ),
    "gost_calculated_car_capacity": (
        r"P_{\mathrm{к}}=\operatorname{окр}_{0{,}5\uparrow}"
        r"(P_{\mathrm{ном}}k_{\mathrm{з}})"
    ),
    "gost_passenger_transfer_time": (
        r"t_{\mathrm{в}}=\operatorname{табл.3}(b_{\mathrm{двери}})"
    ),
    "gost_probable_stops": (
        r"S=N_{\mathrm{эт}}\left[1-\left(1-\frac{1}{N_{\mathrm{эт}}}\right)"
        r"^{P_{\mathrm{к}}}\right]"
    ),
    "gost_reversal_floor": (
        r"N_{\mathrm{р}}=N_{\mathrm{эт}}-"
        r"\sum_{i=1}^{N_{\mathrm{эт}}-1}"
        r"\left(\frac{i}{N_{\mathrm{эт}}}\right)^{P_{\mathrm{к}}}"
    ),
    "gost_adjacent_floor_time": (
        r"t_{\mathrm{эт.н}}=\frac{h_{\mathrm{эт}}}{v_{\mathrm{н}}}"
    ),
    "kinematic_acceleration_distance": (
        r"s_{\mathrm{вм}}=\frac{v_{\mathrm{м}}^2}{2a}"
        r"+\frac{av_{\mathrm{м}}}{2j};\quad 2s_{\mathrm{вм}}\le d_{\mathrm{ф}}"
    ),
    "kinematic_maximum_speed": (
        r"v_{\mathrm{м}}=-\frac{a^2}{2j}"
        r"+\sqrt{ad_{\mathrm{ф}}+\left(\frac{a^2}{2j}\right)^2}"
    ),
    "gost_adjacent_floor_profile_time": (
        r"t_{\mathrm{эт}}=f_S(h_{\mathrm{эт}},v_{\mathrm{н}},a,b,j)"
        r"=t_{\mathrm{разг}}+t_{\mathrm{уст}}+t_{\mathrm{торм}}"
    ),
    "gost_stop_time": (
        r"t_{\mathrm{ост}}=t_{\mathrm{з}}+t_{\mathrm{з.д}}+t_{\mathrm{эт}}"
        r"-t_{\mathrm{пр}}+t_{\mathrm{о}}+t_{\mathrm{з.з}}-t_{\mathrm{эт.н}}"
    ),
    "gost_round_trip_time": (
        r"T=2N_{\mathrm{р}}t_{\mathrm{эт.н}}"
        r"+(S+1)t_{\mathrm{ост}}+2P_{\mathrm{к}}t_{\mathrm{в}}"
    ),
    "gost_interval": r"t_{\mathrm{и}}=\frac{T}{N_{\mathrm{л}}}",
    "gost_group_handling_capacity": (
        r"P_5=\frac{300P_{\mathrm{к}}N_{\mathrm{л}}}{T}"
        r"=\frac{300P_{\mathrm{к}}}{t_{\mathrm{и}}}"
    ),
    "gost_handling_capacity_percent": r"\%P_5=\frac{100P_5}{A}",
    "parking_lower_reversal": (
        r"H_{\mathrm{м}}=\sum_{k=1}^{M}\left[1-\left(1-q_{\mathrm{м}}"
        r"\frac{M-k+1}{M}\right)^{P_{\mathrm{к}}}\right]"
    ),
    "parking_expected_depth": (
        r"D_{\mathrm{м}}=\sum_{k=1}^{M}\Delta h_k\left[1-\left(1-q_{\mathrm{м}}"
        r"\frac{M-k+1}{M}\right)^{P_{\mathrm{к}}}\right]"
    ),
    "parking_probable_stops": (
        r"S_{\mathrm{м}}=M\left[1-\left(1-\frac{q_{\mathrm{м}}}{M}\right)"
        r"^{P_{\mathrm{к}}}\right]"
    ),
    "parking_round_trip_extension": (
        r"T_{\mathrm{м}}=T_{\mathrm{ГОСТ}}+\frac{2D_{\mathrm{м}}}{v_{\mathrm{н}}}"
        r"+S_{\mathrm{м}}t_{\mathrm{ост.м}}"
    ),
}


FORMULA_USAGE = {
    "calculated_car_capacity": (
        "Определяет целое число пассажиров, принимаемое для предварительного "
        "расчёта и ограничения вместимости в симуляции."
    ),
    "probable_stops_uniform": (
        "Оценивает, сколько разных этажей назначения выберут пассажиры одной кабины."
    ),
    "highest_reversal_uniform": (
        "Оценивает наиболее высокий этаж, до которого в среднем поднимется кабина."
    ),
    "motion_time": (
        "Расстояние, скорость, ускорение и замедление определяют длительности "
        "разгона, установившегося движения и торможения; их сумма даёт полное "
        "время поездки."
    ),
    "engineering_cycle_time": (
        "Суммирует движение, остановки и пассажирообмен для одного условного рейса."
    ),
    "interval": "Показывает средний промежуток между отправлениями кабин группы.",
    "handling_capacity_5min": (
        "Показывает, сколько пассажиров группа способна перевезти за пять минут."
    ),
    "average_wait_proxy": (
        "Грубая ориентировочная оценка нижней границы ожидания; фактическое "
        "распределение ожидания определяется симуляцией."
    ),
    "gost_nominal_speed": (
        "Используется при выборе номинальной скорости по высоте подъёма и "
        "рекомендуемому времени движения."
    ),
    "gost_nominal_capacity": (
        "Переводит грузоподъёмность кабины в номинальное число пассажиров из расчёта "
        "75 кг на человека."
    ),
    "gost_calculated_car_capacity": (
        "Определяет принятое число пассажиров в кабине после применения коэффициента "
        "заполнения."
    ),
    "gost_passenger_transfer_time": (
        "Выбирает время входа или выхода одного пассажира по ширине дверного проёма."
    ),
    "gost_probable_stops": (
        "Определяет вероятное число остановок кабины при равномерном распределении "
        "пассажиров по этажам."
    ),
    "gost_reversal_floor": (
        "Определяет средний наивысший этаж назначения в круговом рейсе."
    ),
    "gost_adjacent_floor_time": (
        "Определяет условное время прохождения одного этажа на номинальной скорости."
    ),
    "kinematic_acceleration_distance": (
        "Проверяет, хватает ли половины межэтажного пролёта для разгона до "
        "номинальной скорости при симметричном S-образном профиле. Если "
        "2sвм больше dф, номинальная скорость на пролёте не достигается."
    ),
    "kinematic_maximum_speed": (
        "Определяет фактически достижимую максимальную скорость между соседними "
        "этажами, когда номинальная скорость недостижима. Формула применяется "
        "для симметричных ускорения и замедления; общий расчёт приложения также "
        "поддерживает разные значения этих параметров."
    ),
    "gost_adjacent_floor_profile_time": (
        "Высота пролёта, скорость, ускорение, замедление и рывок определяют "
        "длительности фаз S-образного профиля. Если кабина не успевает набрать "
        "номинальную скорость, участок установившегося движения равен нулю."
    ),
    "gost_stop_time": (
        "Объединяет работу дверей, задержку пуска и поправку на межэтажное движение."
    ),
    "gost_round_trip_time": (
        "Определяет продолжительность полного расчётного рейса от основного этажа "
        "и обратно."
    ),
    "gost_interval": "Определяет расчётный интервал движения лифтов группы.",
    "gost_group_handling_capacity": (
        "Определяет число пассажиров, перевозимых группой за пять минут."
    ),
    "gost_handling_capacity_percent": (
        "Переводит пятиминутную провозную способность в процент населения "
        "обслуживаемой зоны."
    ),
    "parking_lower_reversal": (
        "Оценивает самый глубокий уровень паркинга, посещаемый за рейс, с учётом "
        "доли пассажиров, прибывающих через паркинг. В расчёте по ГОСТ доля "
        "принимается равной 100%, то есть паркинг участвует в каждом рейсе; "
        "предварительный расчёт использует фактическую долю. Это инженерное "
        "расширение, а не формула ГОСТ."
    ),
    "parking_expected_depth": (
        "Переводит вероятный нижний реверс в физическую глубину по фактическим "
        "отметкам подземных этажей. Это инженерное расширение, а не формула ГОСТ."
    ),
    "parking_probable_stops": (
        "Оценивает число различных парковочных уровней, на которых кабина "
        "остановится за рейс. Для расчёта по ГОСТ используется консервативное "
        "допущение обязательного заезда; точная доля применяется в предварительном "
        "расчёте и симуляции. Это инженерное расширение, а не формула ГОСТ."
    ),
    "parking_round_trip_extension": (
        "Добавляет к круговому рейсу по ГОСТ время спуска и подъёма по паркингу, "
        "а также парковочные остановки. Поправка не является формулой ГОСТ; "
        "результат рекомендуется проверить симуляцией."
    ),
}


PROFILE_EXAMPLES = {
    "up_peak": (
        "Будний день, 08:30–09:30: сотрудники офисного центра прибывают через "
        "вестибюль и поднимаются на рабочие этажи."
    ),
    "down_peak": (
        "Будний день, 18:00–19:00: сотрудники покидают офисные этажи и едут "
        "к основному выходу."
    ),
    "lunch": (
        "Офис с общей столовой, 12:00–14:00: часть пассажиров спускается, часть "
        "возвращается, часть перемещается между подразделениями."
    ),
    "mixed": (
        "Многофункциональный комплекс днём: одновременно работают офисы, сервисы "
        "и общественные помещения, поэтому одного преобладающего направления нет."
    ),
    "bidirectional": (
        "Общественное здание между пиками: примерно одинаковое число посетителей "
        "прибывает и покидает здание."
    ),
    "hotel_morning": (
        "Гостиница, 07:00–10:00: гости едут из номеров к завтраку, выходу и зоне "
        "выезда."
    ),
    "hotel_evening": (
        "Гостиница, 17:00–21:00: прибывающие гости регистрируются и поднимаются "
        "от вестибюля к номерам."
    ),
    "residential_morning": (
        "Жилой дом, 07:00–09:00: жители спускаются из квартир к выходу и паркингу."
    ),
    "residential_evening": (
        "Жилой дом, 18:00–21:00: жители возвращаются и поднимаются от входа или "
        "паркинга к квартирам."
    ),
    "custom": (
        "Используется при наличии обследования объекта, данных СКУД или задания "
        "заказчика с собственными долями направлений."
    ),
}


BUILDING_PROFILE_GUIDE = {
    BuildingType.RESIDENTIAL.value: {
        "default": "Жилой утренний поток",
        "profiles": "Жилой утренний; жилой вечерний; смешанный",
        "description": (
            "Утром обычно преобладает движение с жилых этажей вниз, вечером — "
            "от входа и паркинга вверх. Смешанный профиль применяют для дневного "
            "периода, выходных или дома с активными общественными помещениями."
        ),
        "example": "Многоквартирный дом с одним вестибюлем и подземным паркингом.",
    },
    BuildingType.OFFICE.value: {
        "default": "Утренний восходящий пик",
        "profiles": "Утренний восходящий; вечерний нисходящий; обеденный",
        "description": (
            "До начала рабочего дня основной поток идёт от входа вверх, после "
            "окончания работы — вниз. Для здания со столовой или общими переговорными "
            "дополнительно проверяют обеденный и межэтажный потоки."
        ),
        "example": "Офисный центр с рабочим графиком 09:00–18:00.",
    },
    BuildingType.HOTEL.value: {
        "default": "Гостиничный утренний поток",
        "profiles": "Гостиничный утренний; гостиничный вечерний; смешанный",
        "description": (
            "Утром преобладают поездки из номеров вниз, вечером — от вестибюля "
            "к номерам. Смешанный профиль нужен для гостиницы с конференц-залами, "
            "ресторанами или активным дневным заселением."
        ),
        "example": "Городская гостиница с рестораном на первом этаже.",
    },
    BuildingType.MIXED_USE.value: {
        "default": "Смешанный поток",
        "profiles": "Отдельный профиль для каждой функциональной зоны",
        "description": (
            "Жилую, офисную, гостиничную и общественную части следует рассматривать "
            "раздельно. Для общей лифтовой группы итоговый поток получают объединением "
            "зон и проверяют симуляцией."
        ),
        "example": "Комплекс с жильём, офисами и торговыми помещениями на стилобате.",
    },
    BuildingType.CUSTOM.value: {
        "default": "Пользовательский сценарий",
        "profiles": "По заданию заказчика или данным обследования",
        "description": (
            "Применяется, когда назначение объекта не соответствует типовым категориям "
            "или известны собственные доли и временная структура пассажиропотока."
        ),
        "example": "Больница, учебный корпус, транспортный узел или объект со сменным режимом.",
    },
}


ARRIVAL_DISTRIBUTION_GUIDE = {
    ArrivalDistribution.POISSON.value: {
        "description": "Случайные независимые приходы при постоянной средней интенсивности.",
        "example": "Обычный поток посетителей в течение стабильного пятиминутного периода.",
    },
    ArrivalDistribution.NONSTATIONARY_POISSON.value: {
        "description": "Случайный поток, интенсивность которого меняется во времени.",
        "example": "Нарастание офисного пика к 09:00 и постепенное снижение после него.",
    },
    ArrivalDistribution.PROFILE.value: {
        "description": "Период разбит на интервалы с заранее заданными долями нагрузки.",
        "example": "Известная почасовая диаграмма СКУД или профиль по результатам обследования.",
    },
    ArrivalDistribution.DETERMINISTIC.value: {
        "description": "Пассажиры появляются через одинаковые интервалы без случайного разброса.",
        "example": "Контрольное сравнение двух вариантов в полностью одинаковых условиях.",
    },
    ArrivalDistribution.IMPORTED.value: {
        "description": "Воспроизводится подготовленный список событий прибытия и назначения.",
        "example": "Повтор фактически измеренного пассажиропотока для верификации модели.",
    },
    ArrivalDistribution.BATCH.value: {
        "description": "Пассажиры прибывают одновременно группами.",
        "example": "Окончание мероприятия, прибытие автобуса или пропуск группы через турникеты.",
    },
}
