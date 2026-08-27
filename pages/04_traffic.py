"""Настройка сценария пассажиропотока."""

from __future__ import annotations

import streamlit as st

from src.models.traffic import ArrivalDistribution, TrafficScenario, TrafficScenarioType
from src.ui import configure_page, ensure_session, update_project
from src.utils.traffic_profiles import (
    traffic_profile_description,
    traffic_profile_preset,
)
from src.utils.traffic_shares import shares_from_incoming, shares_from_interfloor


ARRIVAL_DISTRIBUTION_DESCRIPTIONS = {
    ArrivalDistribution.POISSON: (
        "Случайный поток с постоянной средней интенсивностью. Подходит для обычного "
        "пассажиропотока, когда известен ожидаемый объём, но неизвестны точные моменты прихода."
    ),
    ArrivalDistribution.NONSTATIONARY_POISSON: (
        "Пуассоновский поток с меняющейся во времени интенсивностью. Нужен для периодов, "
        "в которых спрос нарастает или снижается; изменение задаётся временным профилем."
    ),
    ArrivalDistribution.PROFILE: (
        "Период делится на интервалы с заданными долями интенсивности. Используется, "
        "когда известна форма нагрузки по времени, например пик в начале пятиминутки."
    ),
    ArrivalDistribution.DETERMINISTIC: (
        "Пассажиры приходят через одинаковые интервалы без случайного разброса. Удобно "
        "для контрольных прогонов и сравнения конфигураций в одинаковых условиях."
    ),
    ArrivalDistribution.IMPORTED: (
        "Каждый пассажир берётся из подготовленного списка с временем прибытия, этажом "
        "отправления и этажом назначения. Нужен для воспроизведения измеренного потока."
    ),
    ArrivalDistribution.BATCH: (
        "Пассажиры поступают одновременно группами по три человека. Модель подходит "
        "для залповых прибытий после проходной, автобуса, поезда или окончания мероприятия."
    ),
}

BURSTS_DESCRIPTION = (
    "Добавляет к базовому пуассоновскому потоку дополнительное случайное число пассажиров "
    "со средним объёмом около 10% расчётного спроса. Используется как нагрузочная проверка "
    "очередей и времени ожидания. Для остальных моделей распределения настройка не применяется."
)

DIRECTION_PERCENT_KEYS = (
    "traffic_incoming_percent",
    "traffic_outgoing_percent",
    "traffic_interfloor_percent",
)
PARKING_PERCENT_KEY = "traffic_parking_incoming_percent"
POPULATION_PERCENT_KEY = "traffic_population_percent_5min"
SCENARIO_TYPE_KEY = "traffic_scenario_type"
ARRIVAL_DISTRIBUTION_KEY = "traffic_arrival_distribution"
RANDOM_BURSTS_KEY = "traffic_random_bursts"
GOST_SCENARIO_LABEL = "По ГОСТ"
GOST_SCENARIO_DESCRIPTION = (
    "Нормативный восходящий пассажиропоток для расчёта по ГОСТ 34758-2021. "
    "Приложение автоматически принимает 100% входящего потока и нормативный "
    "пятиминутный процент для выбранного типа здания."
)


def is_gost_scenario(value: TrafficScenarioType | str) -> bool:
    """Распознаёт сценарий ГОСТ без обращения к новому члену enum.

    Это сохраняет работу страницы при частичном горячем обновлении Streamlit,
    когда модуль с перечислением ещё остался в памяти от предыдущей версии.
    """

    return getattr(value, "value", value) == GOST_SCENARIO_LABEL


def update_shares_from_incoming() -> None:
    """Сбрасывает межэтажный поток и рассчитывает исходящий."""

    balanced = shares_from_incoming(
        int(round(st.session_state[DIRECTION_PERCENT_KEYS[0]]))
    )
    for key, value in zip(DIRECTION_PERCENT_KEYS, balanced, strict=True):
        st.session_state[key] = value


def update_shares_from_interfloor() -> None:
    """Сохраняет входящий поток и рассчитывает исходящий по остатку."""

    balanced = shares_from_interfloor(
        int(round(st.session_state[DIRECTION_PERCENT_KEYS[0]])),
        int(round(st.session_state[DIRECTION_PERCENT_KEYS[2]])),
    )
    for key, value in zip(DIRECTION_PERCENT_KEYS, balanced, strict=True):
        st.session_state[key] = value


def apply_selected_scenario_profile() -> None:
    """Подставляет стартовые параметры после смены типового сценария."""

    selected = st.session_state[SCENARIO_TYPE_KEY]
    profile_type = (
        TrafficScenarioType.UP_PEAK
        if is_gost_scenario(selected)
        else selected
    )
    if not isinstance(profile_type, TrafficScenarioType):
        profile_type = TrafficScenarioType(profile_type)
    preset = traffic_profile_preset(
        profile_type,
        project.building.building_type,
        float(st.session_state[POPULATION_PERCENT_KEY]),
    )
    if preset is None:
        return
    st.session_state[DIRECTION_PERCENT_KEYS[0]] = preset.incoming_percent
    st.session_state[DIRECTION_PERCENT_KEYS[1]] = preset.outgoing_percent
    st.session_state[DIRECTION_PERCENT_KEYS[2]] = preset.interfloor_percent
    st.session_state[POPULATION_PERCENT_KEY] = preset.population_percent_5min
    if is_gost_scenario(selected):
        st.session_state[ARRIVAL_DISTRIBUTION_KEY] = ArrivalDistribution.POISSON
        st.session_state[RANDOM_BURSTS_KEY] = False


configure_page("Пассажиропоток")
project = ensure_session()
st.title("4. Пассажиропоток")
scenario = project.scenario()
parking_floors = [floor for floor in project.floors if floor.is_parking]

scenario_signature = (
    scenario.id,
    scenario.name,
    scenario.scenario_type.value,
    scenario.population_percent_5min,
    scenario.incoming_share,
    scenario.outgoing_share,
    scenario.interfloor_share,
    scenario.parking_incoming_share,
)
if (
    st.session_state.get("traffic_direction_scenario_signature")
    != scenario_signature
):
    initial_incoming = round(scenario.incoming_share * 100)
    initial_interfloor = min(
        round(scenario.interfloor_share * 100),
        100 - initial_incoming,
    )
    initial_shares = shares_from_interfloor(
        initial_incoming,
        initial_interfloor,
    )
    for key, value in zip(DIRECTION_PERCENT_KEYS, initial_shares, strict=True):
        st.session_state[key] = value
    st.session_state[PARKING_PERCENT_KEY] = round(
        scenario.parking_incoming_share * 100
    )
    st.session_state[POPULATION_PERCENT_KEY] = float(
        scenario.population_percent_5min
    )
    st.session_state[SCENARIO_TYPE_KEY] = (
        GOST_SCENARIO_LABEL
        if scenario.name == GOST_SCENARIO_LABEL
        else scenario.scenario_type
    )
    st.session_state[ARRIVAL_DISTRIBUTION_KEY] = scenario.arrival_distribution
    st.session_state[RANDOM_BURSTS_KEY] = scenario.random_bursts
    st.session_state.traffic_direction_scenario_signature = scenario_signature
st.session_state.setdefault(
    PARKING_PERCENT_KEY,
    round(scenario.parking_incoming_share * 100),
)
st.session_state.setdefault(
    POPULATION_PERCENT_KEY,
    float(scenario.population_percent_5min),
)
st.session_state.setdefault(
    SCENARIO_TYPE_KEY,
    (
        GOST_SCENARIO_LABEL
        if scenario.name == GOST_SCENARIO_LABEL
        else scenario.scenario_type
    ),
)
if is_gost_scenario(st.session_state[SCENARIO_TYPE_KEY]):
    st.session_state[SCENARIO_TYPE_KEY] = GOST_SCENARIO_LABEL
st.session_state.setdefault(
    ARRIVAL_DISTRIBUTION_KEY,
    scenario.arrival_distribution,
)
st.session_state.setdefault(RANDOM_BURSTS_KEY, scenario.random_bursts)

with st.container(border=True):
    left, right = st.columns(2)
    with left:
        types = [
            GOST_SCENARIO_LABEL,
            *[
                item
                for item in TrafficScenarioType
                if not is_gost_scenario(item)
            ],
        ]
        scenario_type = st.selectbox(
            "Тип сценария",
            types,
            format_func=lambda value: getattr(value, "value", value),
            key=SCENARIO_TYPE_KEY,
            on_change=apply_selected_scenario_profile,
            help=(
                "Типичный режим движения пассажиров. При смене сценария приложение "
                "подставляет рекомендуемые доли направлений и пятиминутный процент."
            ),
        )
        gost_scenario_selected = is_gost_scenario(scenario_type)
        st.caption(
            GOST_SCENARIO_DESCRIPTION
            if gost_scenario_selected
            else traffic_profile_description(scenario_type)
        )
        if gost_scenario_selected:
            st.caption(
                "Нормативные параметры установлены автоматически и защищены от "
                "редактирования. Для ручной настройки выберите другой тип сценария."
            )
        distributions = list(ArrivalDistribution)
        distribution = st.selectbox(
            "Распределение поступления",
            distributions,
            format_func=lambda value: value.value,
            key=ARRIVAL_DISTRIBUTION_KEY,
            disabled=gost_scenario_selected,
            help=(
                "Математическая модель моментов появления пассажиров. Она влияет "
                "на очереди и ожидание в симуляции, но не меняет расчётные формулы ГОСТ."
            ),
        )
        st.caption(ARRIVAL_DISTRIBUTION_DESCRIPTIONS[distribution])
    with right:
        population_percent = st.number_input(
            "Процент населения за 5 минут",
            min_value=0.0,
            step=1.0,
            key=POPULATION_PERCENT_KEY,
            disabled=gost_scenario_selected,
            help=(
                "Доля суммарного населения здания, создающая поездки за пять минут. "
                "По этому значению автоматически рассчитывается число пассажиров."
            ),
        )
        random_bursts = st.checkbox(
            "Учитывать всплески",
            key=RANDOM_BURSTS_KEY,
            disabled=gost_scenario_selected,
            help=(
                "Добавляет к пуассоновскому потоку случайные кратковременные "
                "поступления пассажиров для нагрузочной проверки."
            ),
        )
        st.caption(BURSTS_DESCRIPTION)
    st.markdown("**Доли направлений**")
    c1, c2, c3 = st.columns(3)
    incoming_percent = c1.slider(
        "Входящий поток, %",
        min_value=0,
        max_value=100,
        step=1,
        format="%d%%",
        key=DIRECTION_PERCENT_KEYS[0],
        on_change=update_shares_from_incoming,
        disabled=gost_scenario_selected,
        help=(
            "Доля поездок от основного входа или паркинга к верхним этажам. "
            "При изменении исходящий поток пересчитывается автоматически."
        ),
    )
    outgoing_percent = c2.slider(
        "Исходящий поток, % (автоматически)",
        min_value=0,
        max_value=100,
        step=1,
        format="%d%%",
        key=DIRECTION_PERCENT_KEYS[1],
        disabled=True,
        help=(
            "Доля поездок с этажей к основному выходу. Рассчитывается как остаток "
            "после входящего и межэтажного потоков."
        ),
    )
    maximum_interfloor = 100 - incoming_percent
    interfloor_percent = c3.slider(
        "Межэтажный поток, %",
        min_value=0,
        max_value=max(1, maximum_interfloor),
        step=1,
        format="%d%%",
        key=DIRECTION_PERCENT_KEYS[2],
        on_change=update_shares_from_interfloor,
        disabled=gost_scenario_selected or maximum_interfloor == 0,
        help=(
            "Доля поездок между этажами без выхода из здания. При её изменении "
            "входящий поток сохраняется, а исходящий пересчитывается."
        ),
    )
    direction_total = incoming_percent + outgoing_percent + interfloor_percent
    bar_total = direction_total if direction_total > 0 else 1.0
    incoming_width = incoming_percent / bar_total * 100.0
    outgoing_width = outgoing_percent / bar_total * 100.0
    interfloor_width = interfloor_percent / bar_total * 100.0
    st.markdown(
        f"""
        <div style="display:flex;height:18px;border-radius:9px;overflow:hidden;
                    background:#e8edf1;margin-top:0.25rem">
          <div title="Входящий поток — {incoming_percent:.0f}%"
               style="width:{incoming_width:.4f}%;background:#1f77b4"></div>
          <div title="Исходящий поток — {outgoing_percent:.0f}%"
               style="width:{outgoing_width:.4f}%;background:#ff7f0e"></div>
          <div title="Межэтажный поток — {interfloor_percent:.0f}%"
               style="width:{interfloor_width:.4f}%;background:#2ca02c"></div>
        </div>
        <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:0.35rem;
                    color:rgba(49,51,63,.72);font-size:.85rem">
          <span><b style="color:#1f77b4">■</b> Входящий {incoming_percent:.0f}%</span>
          <span><b style="color:#ff7f0e">■</b> Исходящий {outgoing_percent:.0f}%</span>
          <span><b style="color:#2ca02c">■</b> Межэтажный {interfloor_percent:.0f}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div aria-hidden="true" style="height:0.55rem"></div>',
        unsafe_allow_html=True,
    )
    if abs(direction_total - 100.0) > 1e-6:
        st.warning(f"Сумма долей: {direction_total:.0f}%. Для сохранения требуется 100%.")
    if parking_floors:
        parking_percent = st.slider(
            "Доля входящего потока с паркинга, %",
            min_value=0,
            max_value=100,
            step=1,
            format="%d%%",
            key=PARKING_PERCENT_KEY,
            help=(
                "Часть входящего потока, начинающая поездку на этажах паркинга. "
                "Она выделяется из общего входящего потока и не увеличивает его сумму."
            ),
        )
        st.caption(
            "Эта доля не добавляется к общему потоку, а выделяется из входящего: "
            f"{parking_percent}% пассажиров начинают поездку на парковочных этажах, "
            f"остальные {100 - parking_percent}% — на основном входном этаже. "
            "Обычный ориентир для проекта — 10–20%. Предварительный расчёт и "
            "симуляция используют указанную долю точно. В расчёте по ГОСТ "
            "применяется консервативное допущение: паркинг участвует в каждом рейсе."
        )
    else:
        parking_percent = 0
        st.caption(
            "Чтобы учитывать поток с паркинга, добавьте подземные этажи в разделе "
            "«2. Этажи» и отметьте их флажком «Паркинг»."
        )
    submitted = st.button(
        "Сохранить сценарий",
        type="primary",
        disabled=abs(direction_total - 100.0) > 1e-6,
        help=(
            "Сохраняет выбранный сценарий, модель поступления, пятиминутный спрос "
            "и доли направлений для последующих расчётов и симуляции."
        ),
    )

if submitted:
    try:
        stored_scenario_type = (
            TrafficScenarioType.UP_PEAK
            if gost_scenario_selected
            else scenario_type
        )
        updated = TrafficScenario(
            **{
                **scenario.model_dump(),
                "name": (
                    GOST_SCENARIO_LABEL
                    if gost_scenario_selected
                    else scenario_type.value
                ),
                "scenario_type": stored_scenario_type,
                "arrival_distribution": distribution,
                "five_minute_passengers": None,
                "population_percent_5min": float(population_percent),
                "incoming_share": float(incoming_percent) / 100.0,
                "outgoing_share": float(outgoing_percent) / 100.0,
                "interfloor_share": float(interfloor_percent) / 100.0,
                "parking_incoming_share": (
                    float(parking_percent) / 100.0
                    if parking_floors
                    else scenario.parking_incoming_share
                ),
                "random_bursts": random_bursts,
            }
        )
        candidate = project.model_copy(deep=True)
        index = next(i for i, item in enumerate(candidate.traffic_scenarios) if item.id == scenario.id)
        candidate.traffic_scenarios[index] = updated
        candidate.active_scenario_id = updated.id
        update_project(candidate)
        st.success("Сценарий сохранён.")
    except Exception as exc:
        st.error(f"Не удалось сохранить сценарий: {exc}")

with st.expander("Чем отличаются модели поступления"):
    for distribution_type, description in ARRIVAL_DISTRIBUTION_DESCRIPTIONS.items():
        st.markdown(f"**{distribution_type.value}.** {description}")
    st.markdown(f"**Учитывать всплески.** {BURSTS_DESCRIPTION}")

calculated_five_minute_flow = round(
    project.population * float(population_percent) / 100
)
parking_five_minute_flow = round(
    calculated_five_minute_flow
    * float(incoming_percent)
    / 100
    * float(parking_percent)
    / 100
)
st.metric(
    "Расчётный поток за 5 минут",
    f"{calculated_five_minute_flow} пассажиров",
    help=(
        "Суммарное население здания, умноженное на выбранный процент населения "
        "за пять минут. Показатель обновляется до сохранения сценария."
    ),
)
if parking_floors:
    st.caption(
        f"Из них ориентировочно {parking_five_minute_flow} пассажиров начинают "
        f"поездку с паркинга ({', '.join(str(floor.number) for floor in parking_floors)})."
    )
st.caption(
    "Показатель пересчитывается сразу по текущему населению здания и выбранному проценту."
)
