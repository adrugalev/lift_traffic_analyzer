"""Прозрачный расчёт ГОСТ 34758-2021 и инженерный preview."""

from __future__ import annotations

import math
from statistics import mean

from src import __version__
from src.models.building import BuildingType, StandardSelection
from src.models.elevator import Elevator, ElevatorGroup
from src.models.project import Project
from src.models.results import (
    AuditRecord,
    CalculationResult,
    ComplianceStatus,
    DiagnosticMessage,
    FormulaTrace,
    MessageSeverity,
    MetricResult,
)
from src.models.traffic import TrafficScenarioType
from src.services.configuration_service import ConfigurationService
from src.services.formula_service import FormulaService
from src.services.validation_service import ValidationService
from src.utils.hashing import project_hash


class NormativeConfigurationError(RuntimeError):
    """Нормативный расчёт запрошен без верифицированной конфигурации."""


def calculated_capacity(nominal_passengers: int, load_factor: float) -> int:
    """Округляет расчётную вместимость до ближайшего целого, половины вверх."""

    if nominal_passengers <= 0:
        raise ValueError("Номинальная вместимость должна быть больше нуля.")
    if not 0 < load_factor <= 1:
        raise ValueError("Коэффициент заполнения должен быть в диапазоне (0; 1].")
    return min(
        nominal_passengers,
        max(1, math.floor(nominal_passengers * load_factor + 0.5)),
    )


def probable_stops_uniform(destination_floors: int, passengers: float) -> float:
    """Оценивает число уникальных остановок при равномерном выборе этажей."""

    if destination_floors <= 0 or passengers <= 0:
        return 0.0
    return destination_floors * (1.0 - ((destination_floors - 1.0) / destination_floors) ** passengers)


def expected_highest_reversal(destination_floors: int, passengers: float) -> float:
    """Оценивает максимальный выбранный этаж для равномерного распределения."""

    if destination_floors <= 0 or passengers <= 0:
        return 0.0
    return sum(
        1.0 - ((floor_index - 1.0) / destination_floors) ** passengers
        for floor_index in range(1, destination_floors + 1)
    )


def expected_parking_lower_reversal(
    parking_levels: int,
    car_passengers: float,
    parking_share: float,
) -> float:
    """Оценивает глубину нижнего реверса с учётом доли пассажиров паркинга."""

    if parking_levels <= 0 or car_passengers <= 0 or parking_share <= 0:
        return 0.0
    if parking_share > 1:
        raise ValueError("Доля пассажиров с паркинга не может превышать единицу.")
    return sum(
        1.0
        - (
            1.0
            - parking_share
            * (parking_levels - level_index + 1.0)
            / parking_levels
        )
        ** car_passengers
        for level_index in range(1, parking_levels + 1)
    )


def probable_parking_stops(
    parking_levels: int,
    car_passengers: float,
    parking_share: float,
) -> float:
    """Оценивает число разных парковочных этажей, посещаемых за рейс."""

    if parking_levels <= 0 or car_passengers <= 0 or parking_share <= 0:
        return 0.0
    if parking_share > 1:
        raise ValueError("Доля пассажиров с паркинга не может превышать единицу.")
    return parking_levels * (
        1.0 - (1.0 - parking_share / parking_levels) ** car_passengers
    )


def expected_parking_depth(
    parking_depths_m: list[float],
    car_passengers: float,
    parking_share: float,
) -> float:
    """Оценивает максимальную глубину заезда по фактическим отметкам паркинга."""

    depths = sorted(float(depth) for depth in parking_depths_m if depth > 0)
    if not depths or car_passengers <= 0 or parking_share <= 0:
        return 0.0
    if parking_share > 1:
        raise ValueError("Доля пассажиров с паркинга не может превышать единицу.")

    parking_levels = len(depths)
    expected_depth = 0.0
    previous_depth = 0.0
    for index, depth in enumerate(depths):
        levels_at_or_below = parking_levels - index
        probability_reaching_depth = 1.0 - (
            1.0 - parking_share * levels_at_or_below / parking_levels
        ) ** car_passengers
        expected_depth += (depth - previous_depth) * probability_reaching_depth
        previous_depth = depth
    return expected_depth


def travel_time_phases(
    distance_m: float,
    speed_mps: float,
    acceleration_mps2: float,
    deceleration_mps2: float,
) -> tuple[float, float, float]:
    """Возвращает времена разгона, установившегося движения и торможения."""

    if distance_m < 0:
        raise ValueError("Расстояние не может быть отрицательным.")
    if distance_m == 0:
        return 0.0, 0.0, 0.0
    if min(speed_mps, acceleration_mps2, deceleration_mps2) <= 0:
        raise ValueError("Скорость, ускорение и замедление должны быть больше нуля.")
    acceleration_distance = speed_mps**2 / (2.0 * acceleration_mps2)
    deceleration_distance = speed_mps**2 / (2.0 * deceleration_mps2)
    if acceleration_distance + deceleration_distance <= distance_m:
        cruise_distance = distance_m - acceleration_distance - deceleration_distance
        return (
            speed_mps / acceleration_mps2,
            cruise_distance / speed_mps,
            speed_mps / deceleration_mps2,
        )
    peak_speed = math.sqrt(
        2.0 * distance_m / (1.0 / acceleration_mps2 + 1.0 / deceleration_mps2)
    )
    return (
        peak_speed / acceleration_mps2,
        0.0,
        peak_speed / deceleration_mps2,
    )


def travel_time(
    distance_m: float,
    speed_mps: float,
    acceleration_mps2: float,
    deceleration_mps2: float,
) -> float:
    """Рассчитывает время по треугольному или трапецеидальному профилю скорости."""

    return sum(
        travel_time_phases(
            distance_m,
            speed_mps,
            acceleration_mps2,
            deceleration_mps2,
        )
    )


def _jerk_limited_velocity_change(
    peak_speed_mps: float,
    maximum_acceleration_mps2: float,
    jerk_mps3: float,
) -> tuple[float, float]:
    """Возвращает путь и время симметричного S-профиля от 0 до заданной скорости."""

    acceleration_threshold_speed = maximum_acceleration_mps2**2 / jerk_mps3
    if peak_speed_mps <= acceleration_threshold_speed:
        phase_time = 2.0 * math.sqrt(peak_speed_mps / jerk_mps3)
    else:
        phase_time = (
            peak_speed_mps / maximum_acceleration_mps2
            + maximum_acceleration_mps2 / jerk_mps3
        )
    return 0.5 * peak_speed_mps * phase_time, phase_time


def jerk_limited_transition_distance(
    peak_speed_mps: float,
    maximum_acceleration_mps2: float,
    jerk_mps3: float,
) -> float:
    """Возвращает путь S-образного разгона от нуля до заданной скорости."""

    if min(peak_speed_mps, maximum_acceleration_mps2, jerk_mps3) <= 0:
        raise ValueError("Скорость, ускорение и рывок должны быть больше нуля.")
    return _jerk_limited_velocity_change(
        peak_speed_mps,
        maximum_acceleration_mps2,
        jerk_mps3,
    )[0]


def jerk_limited_peak_speed(
    distance_m: float,
    speed_mps: float,
    acceleration_mps2: float,
    deceleration_mps2: float,
    jerk_mps3: float,
) -> float:
    """Возвращает максимальную достижимую скорость на заданном пролёте."""

    if distance_m < 0:
        raise ValueError("Расстояние не может быть отрицательным.")
    if distance_m == 0:
        return 0.0
    if min(speed_mps, acceleration_mps2, deceleration_mps2, jerk_mps3) <= 0:
        raise ValueError(
            "Скорость, ускорение, замедление и рывок должны быть больше нуля."
        )

    acceleration_distance = jerk_limited_transition_distance(
        speed_mps, acceleration_mps2, jerk_mps3
    )
    deceleration_distance = jerk_limited_transition_distance(
        speed_mps, deceleration_mps2, jerk_mps3
    )
    if acceleration_distance + deceleration_distance <= distance_m:
        return speed_mps

    lower_speed = 0.0
    upper_speed = speed_mps
    for _ in range(100):
        peak_speed = (lower_speed + upper_speed) / 2.0
        acceleration_distance = _jerk_limited_velocity_change(
            peak_speed, acceleration_mps2, jerk_mps3
        )[0]
        deceleration_distance = _jerk_limited_velocity_change(
            peak_speed, deceleration_mps2, jerk_mps3
        )[0]
        if acceleration_distance + deceleration_distance < distance_m:
            lower_speed = peak_speed
        else:
            upper_speed = peak_speed
    return (lower_speed + upper_speed) / 2.0


def jerk_limited_travel_phases(
    distance_m: float,
    speed_mps: float,
    acceleration_mps2: float,
    deceleration_mps2: float,
    jerk_mps3: float,
) -> tuple[float, float, float]:
    """Возвращает времена разгона, установившегося движения и торможения S-профиля.

    Если номинальная скорость на заданном пролёте недостижима, пиковая скорость
    находится двоичным поиском из условия равенства пути разгону и торможению.
    """

    if distance_m < 0:
        raise ValueError("Расстояние не может быть отрицательным.")
    if distance_m == 0:
        return 0.0, 0.0, 0.0
    if min(speed_mps, acceleration_mps2, deceleration_mps2, jerk_mps3) <= 0:
        raise ValueError(
            "Скорость, ускорение, замедление и рывок должны быть больше нуля."
        )

    peak_speed = jerk_limited_peak_speed(
        distance_m,
        speed_mps,
        acceleration_mps2,
        deceleration_mps2,
        jerk_mps3,
    )
    acceleration_distance, acceleration_time = _jerk_limited_velocity_change(
        peak_speed, acceleration_mps2, jerk_mps3
    )
    deceleration_distance, deceleration_time = _jerk_limited_velocity_change(
        peak_speed, deceleration_mps2, jerk_mps3
    )
    transition_distance = acceleration_distance + deceleration_distance
    cruise_time = max(0.0, distance_m - transition_distance) / peak_speed
    return acceleration_time, cruise_time, deceleration_time


def jerk_limited_travel_time(
    distance_m: float,
    speed_mps: float,
    acceleration_mps2: float,
    deceleration_mps2: float,
    jerk_mps3: float,
) -> float:
    """Рассчитывает полное время идеального S-профиля."""

    return sum(
        jerk_limited_travel_phases(
            distance_m,
            speed_mps,
            acceleration_mps2,
            deceleration_mps2,
            jerk_mps3,
        )
    )


def nominal_passengers_from_capacity(capacity_kg: float) -> int:
    """ГОСТ 34758-2021, п. 6.5.3: Q / 75 с округлением до ближайшего целого."""

    if capacity_kg <= 0:
        raise ValueError("Номинальная грузоподъёмность должна быть больше нуля.")
    return max(1, math.floor(capacity_kg / 75.0 + 0.5))


def passenger_transfer_time(door_width_m: float) -> float:
    """ГОСТ 34758-2021, п. 6.4, таблица 3."""

    values = {800: 1.2, 900: 1.1, 1000: 1.0, 1100: 1.0, 1200: 0.9}
    width_mm = int(round(door_width_m * 1000.0))
    if not math.isclose(door_width_m * 1000.0, width_mm, abs_tol=1e-6) or width_mm not in values:
        raise ValueError(
            "Для расчётного метода ГОСТ ширина дверного проёма должна точно "
            "соответствовать таблице 3: 800, 900, 1000, 1100 или 1200 мм."
        )
    return values[width_mm]


def nominal_speed_for_travel_time(travel_height_m: float, full_height_time_s: float) -> float:
    """ГОСТ 34758-2021, формула (1)."""

    if travel_height_m < 0 or full_height_time_s <= 0:
        raise ValueError("Высота не может быть отрицательной, а время должно быть больше нуля.")
    return travel_height_m / full_height_time_s


def adjacent_floor_nominal_time(floor_height_m: float, speed_mps: float) -> float:
    """ГОСТ 34758-2021, формула (8)."""

    if floor_height_m <= 0 or speed_mps <= 0:
        raise ValueError("Высота этажа и скорость должны быть больше нуля.")
    return floor_height_m / speed_mps


def normative_stop_time(
    door_close_time_s: float,
    start_delay_s: float,
    adjacent_floor_profile_time_s: float,
    pre_open_time_s: float,
    door_open_time_s: float,
    door_close_delay_s: float,
    adjacent_floor_nominal_time_s: float,
) -> float:
    """ГОСТ 34758-2021, формула (9)."""

    values = (
        door_close_time_s,
        start_delay_s,
        adjacent_floor_profile_time_s,
        pre_open_time_s,
        door_open_time_s,
        door_close_delay_s,
        adjacent_floor_nominal_time_s,
    )
    if any(value < 0 for value in values):
        raise ValueError("Временные параметры формулы остановки не могут быть отрицательными.")
    result = (
        door_close_time_s
        + start_delay_s
        + adjacent_floor_profile_time_s
        - pre_open_time_s
        + door_open_time_s
        + door_close_delay_s
        - adjacent_floor_nominal_time_s
    )
    if result <= 0:
        raise ValueError("Время остановки по формуле (9) должно быть больше нуля.")
    return result


def normative_round_trip_time(
    reversal_floor: float,
    adjacent_floor_nominal_time_s: float,
    probable_stops: float,
    stop_time_s: float,
    car_passengers: float,
    passenger_transfer_time_s: float,
) -> float:
    """ГОСТ 34758-2021, формула (7)."""

    if min(
        reversal_floor,
        adjacent_floor_nominal_time_s,
        stop_time_s,
        car_passengers,
        passenger_transfer_time_s,
    ) <= 0 or probable_stops < 0:
        raise ValueError("Параметры времени кругового рейса должны быть положительными.")
    return (
        2.0 * reversal_floor * adjacent_floor_nominal_time_s
        + (probable_stops + 1.0) * stop_time_s
        + 2.0 * car_passengers * passenger_transfer_time_s
    )


def normative_interval(round_trip_time_s: float, elevator_count: int) -> float:
    """ГОСТ 34758-2021, формула (5)."""

    if round_trip_time_s <= 0 or elevator_count <= 0:
        raise ValueError("Время рейса и количество лифтов должны быть больше нуля.")
    return round_trip_time_s / elevator_count


def group_handling_capacity(
    car_passengers: float,
    elevator_count: int,
    round_trip_time_s: float,
) -> float:
    """ГОСТ 34758-2021, формула (4)."""

    if car_passengers <= 0 or elevator_count <= 0 or round_trip_time_s <= 0:
        raise ValueError("Параметры провозной способности должны быть больше нуля.")
    return 300.0 * car_passengers * elevator_count / round_trip_time_s


def handling_capacity_percent(handling_capacity_5min: float, population: float) -> float:
    """ГОСТ 34758-2021, формула (6)."""

    if handling_capacity_5min < 0 or population <= 0:
        raise ValueError("Провозная способность не может быть отрицательной, население должно быть больше нуля.")
    return handling_capacity_5min * 100.0 / population


def _average_elevator(group: ElevatorGroup) -> Elevator:
    """Формирует усреднённые параметры неоднородной группы для preview-расчёта."""

    elevators = group.elevators
    return Elevator(
        name="Усреднённый лифт",
        capacity_kg=mean(item.capacity_kg for item in elevators),
        nominal_passengers=max(1, round(mean(item.nominal_passengers for item in elevators))),
        load_factor=mean(item.load_factor for item in elevators),
        speed_mps=mean(item.speed_mps for item in elevators),
        acceleration_mps2=mean(item.acceleration_mps2 for item in elevators),
        deceleration_mps2=mean(item.deceleration_mps2 for item in elevators),
        jerk_mps3=mean(item.jerk_mps3 for item in elevators),
        door_width_m=mean(item.door_width_m for item in elevators),
        door_open_time_s=mean(item.door_open_time_s for item in elevators),
        door_close_time_s=mean(item.door_close_time_s for item in elevators),
        pre_open_time_s=mean(item.pre_open_time_s for item in elevators),
        door_dwell_time_s=mean(item.door_dwell_time_s for item in elevators),
        control_transfer_time_s=mean(item.control_transfer_time_s for item in elevators),
        boarding_time_per_passenger_s=mean(item.boarding_time_per_passenger_s for item in elevators),
        alighting_time_per_passenger_s=mean(item.alighting_time_per_passenger_s for item in elevators),
        leveling_time_s=mean(item.leveling_time_s for item in elevators),
        start_brake_allowance_s=mean(item.start_brake_allowance_s for item in elevators),
        travel_height_m=mean(item.travel_height_m for item in elevators),
        stops_count=max(1, round(mean(item.stops_count for item in elevators))),
        door_count=max(1, round(mean(item.door_count for item in elevators))),
        accessible=all(item.accessible for item in elevators),
    )


class AnalyticEngine:
    """Выполняет предварительный расчёт и контролирует доступ к нормативному режиму."""

    def __init__(
        self,
        configuration: ConfigurationService | None = None,
        formulas: FormulaService | None = None,
    ) -> None:
        self.configuration = configuration or ConfigurationService()
        self.formulas = formulas or FormulaService(self.configuration)

    def calculate_normative(
        self,
        project: Project,
        group_id: str | None = None,
        *,
        include_extended_kinematics: bool = True,
    ) -> CalculationResult:
        """Выполняет расчётный метод ГОСТ 34758-2021 в его области применимости."""

        if not self.configuration.standard_ready("GOST_34758_2021"):
            raise NormativeConfigurationError("Конфигурация ГОСТ 34758-2021 не активирована.")

        validation_messages = ValidationService.validate_project(project)
        blocking = ValidationService.errors(validation_messages)
        if blocking:
            raise ValueError("Расчёт невозможен: " + " ".join(message.text for message in blocking))

        group = project.group(group_id)
        scenario = project.scenario()
        served = sorted(
            (floor for floor in project.floors if floor.number in group.served_floors),
            key=lambda floor: floor.elevation_m,
        )
        main_floors = [floor for floor in served if floor.number == group.main_floor]
        if len(main_floors) != 1:
            raise NormativeConfigurationError("Основной посадочный этаж не найден в зоне обслуживания.")
        main_floor = main_floors[0]
        parking_floors = [
            floor
            for floor in served
            if floor.number != group.main_floor and floor.is_parking
        ]
        destinations = [
            floor
            for floor in served
            if floor.number != group.main_floor and not floor.is_parking
        ]
        if not destinations:
            raise NormativeConfigurationError(
                "Для расчётного метода нужен хотя бы один этаж назначения."
            )
        normative_floors = [main_floor, *destinations]

        criteria_by_type = self.configuration.standard("GOST_34758_2021").get("criteria", {})
        building_type = project.building.building_type
        if building_type.value not in criteria_by_type:
            raise NormativeConfigurationError(
                "Расчётный метод ГОСТ в текущей реализации применяется только к офису, "
                "гостинице или жилому зданию. Многофункциональный объект разделите на зоны."
            )
        criteria = criteria_by_type[building_type.value]

        scope_errors: list[str] = []
        if scenario.scenario_type is not TrafficScenarioType.UP_PEAK:
            scope_errors.append("выбран не восходящий пиковый пассажиропоток")
        if not (
            math.isclose(scenario.incoming_share, 1.0, abs_tol=1e-9)
            and math.isclose(scenario.outgoing_share, 0.0, abs_tol=1e-9)
            and math.isclose(scenario.interfloor_share, 0.0, abs_tol=1e-9)
        ):
            scope_errors.append("доли потока не соответствуют условию 100% входящих пассажиров")
        if group.entrance_floor_count != 1:
            scope_errors.append("задано более одного входного этажа")
        if main_floor.elevation_m != min(
            floor.elevation_m for floor in normative_floors
        ):
            scope_errors.append("основной посадочный этаж не является нижним")
        if group.elevator_count > 8:
            scope_errors.append("в группе более восьми лифтов")
        if any(elevator.priority_floors for elevator in group.elevators):
            scope_errors.append("заданы приоритетные этажи")
        if "Destination Control" in group.control_type.value:
            scope_errors.append("используется управление с выбором этажа назначения")

        relevant_parameters = (
            "capacity_kg",
            "load_factor",
            "speed_mps",
            "acceleration_mps2",
            "deceleration_mps2",
            "jerk_mps3",
            "door_width_m",
            "door_open_time_s",
            "door_close_time_s",
            "pre_open_time_s",
            "door_dwell_time_s",
            "start_brake_allowance_s",
        )
        reference_elevator = group.elevators[0]
        for elevator in group.elevators[1:]:
            if any(
                not math.isclose(
                    float(getattr(reference_elevator, parameter)),
                    float(getattr(elevator, parameter)),
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                )
                for parameter in relevant_parameters
            ):
                scope_errors.append("лифтовая группа неоднородна")
                break

        elevations = [floor.elevation_m for floor in normative_floors]
        floor_steps = [
            right - left
            for left, right in zip(elevations, elevations[1:], strict=False)
            if right > left
        ]
        if not floor_steps:
            scope_errors.append("невозможно определить высоту этажа")
            average_floor_height = 0.0
        else:
            average_floor_height = mean(floor_steps)
            if any(
                not math.isclose(step, average_floor_height, rel_tol=1e-6, abs_tol=1e-6)
                for step in floor_steps
            ):
                scope_errors.append("высоты между обслуживаемыми этажами неодинаковы")

        destination_populations = [
            project.effective_floor_population(floor)
            for floor in destinations
        ]
        if not destination_populations or min(destination_populations) <= 0:
            scope_errors.append("население этажей назначения должно быть больше нуля")
        elif len(set(destination_populations)) != 1:
            scope_errors.append("этажи назначения заселены неравномерно")

        if scope_errors:
            raise NormativeConfigurationError(
                "Расчётный метод ГОСТ неприменим: "
                + "; ".join(dict.fromkeys(scope_errors))
                + ". Используйте метод моделирования."
            )

        elevator = reference_elevator
        population = float(sum(destination_populations))
        destination_count = len(destinations)
        travel_height = max(elevations) - main_floor.elevation_m
        nominal_capacity = nominal_passengers_from_capacity(elevator.capacity_kg)
        car_passengers = calculated_capacity(nominal_capacity, elevator.load_factor)
        transfer_time = passenger_transfer_time(elevator.door_width_m)
        probable_stops = probable_stops_uniform(destination_count, car_passengers)
        reversal_floor = expected_highest_reversal(destination_count, car_passengers)
        floor_nominal_time = adjacent_floor_nominal_time(
            average_floor_height, elevator.speed_mps
        )
        if include_extended_kinematics:
            nominal_acceleration_distance = jerk_limited_transition_distance(
                elevator.speed_mps,
                elevator.acceleration_mps2,
                elevator.jerk_mps3,
            )
            nominal_deceleration_distance = jerk_limited_transition_distance(
                elevator.speed_mps,
                elevator.deceleration_mps2,
                elevator.jerk_mps3,
            )
            nominal_transition_distance = (
                nominal_acceleration_distance + nominal_deceleration_distance
            )
            adjacent_floor_peak_speed = jerk_limited_peak_speed(
                average_floor_height,
                elevator.speed_mps,
                elevator.acceleration_mps2,
                elevator.deceleration_mps2,
                elevator.jerk_mps3,
            )
            nominal_speed_reached = (
                nominal_transition_distance <= average_floor_height + 1e-9
            )
            floor_motion_phases = jerk_limited_travel_phases(
                average_floor_height,
                elevator.speed_mps,
                elevator.acceleration_mps2,
                elevator.deceleration_mps2,
                elevator.jerk_mps3,
            )
            floor_profile_time = sum(floor_motion_phases)
        else:
            # В формуле (8) ГОСТ используется номинальная скорость. Стандарт
            # не задаёт отдельную зависимость для расчёта пиковой скорости на
            # коротком пролёте, поэтому дополнительные a, b и j здесь не
            # подставляются.
            nominal_acceleration_distance = 0.0
            nominal_deceleration_distance = 0.0
            adjacent_floor_peak_speed = elevator.speed_mps
            nominal_speed_reached = True
            floor_motion_phases = (0.0, floor_nominal_time, 0.0)
            floor_profile_time = floor_nominal_time
        stop_time = normative_stop_time(
            elevator.door_close_time_s,
            elevator.start_brake_allowance_s,
            floor_profile_time,
            elevator.pre_open_time_s,
            elevator.door_open_time_s,
            elevator.door_dwell_time_s,
            floor_nominal_time,
        )
        gost_round_trip_time = normative_round_trip_time(
            reversal_floor,
            floor_nominal_time,
            probable_stops,
            stop_time,
            car_passengers,
            transfer_time,
        )
        parking_share = (
            scenario.parking_incoming_share if parking_floors else 0.0
        )
        parking_extension_active = bool(parking_floors and parking_share > 0)
        # Для консервативной проверки по ГОСТ принимается, что при наличии
        # заданного потока с паркинга каждый расчётный круговой рейс включает
        # паркинг. Фактическая доля используется в предварительном расчёте и
        # симуляции.
        normative_parking_share = 1.0 if parking_extension_active else 0.0
        parking_trip_probability = 0.0
        parking_lower_reversal = 0.0
        parking_stops = 0.0
        parking_depth = 0.0
        parking_floor_nominal_time = 0.0
        parking_floor_profile_time = 0.0
        parking_stop_time = 0.0
        parking_round_trip_addition = 0.0
        round_trip_time = gost_round_trip_time
        if parking_extension_active:
            parking_depths = sorted(
                main_floor.elevation_m - floor.elevation_m
                for floor in parking_floors
                if floor.elevation_m < main_floor.elevation_m
            )
            if not parking_depths:
                parking_extension_active = False
                parking_share = 0.0
            else:
                parking_levels = len(parking_depths)
                parking_trip_probability = 1.0 - (
                    1.0 - normative_parking_share
                ) ** car_passengers
                parking_lower_reversal = expected_parking_lower_reversal(
                    parking_levels,
                    car_passengers,
                    normative_parking_share,
                )
                parking_stops = probable_parking_stops(
                    parking_levels,
                    car_passengers,
                    normative_parking_share,
                )
                parking_depth = expected_parking_depth(
                    parking_depths,
                    car_passengers,
                    normative_parking_share,
                )
                parking_steps = [
                    parking_depths[0],
                    *[
                        right - left
                        for left, right in zip(
                            parking_depths,
                            parking_depths[1:],
                            strict=False,
                        )
                    ],
                ]
                average_parking_floor_height = mean(parking_steps)
                parking_floor_nominal_time = adjacent_floor_nominal_time(
                    average_parking_floor_height,
                    elevator.speed_mps,
                )
                parking_floor_phases = jerk_limited_travel_phases(
                    average_parking_floor_height,
                    elevator.speed_mps,
                    elevator.acceleration_mps2,
                    elevator.deceleration_mps2,
                    elevator.jerk_mps3,
                )
                parking_floor_profile_time = sum(parking_floor_phases)
                parking_stop_time = normative_stop_time(
                    elevator.door_close_time_s,
                    elevator.start_brake_allowance_s,
                    parking_floor_profile_time,
                    elevator.pre_open_time_s,
                    elevator.door_open_time_s,
                    elevator.door_dwell_time_s,
                    parking_floor_nominal_time,
                )
                parking_round_trip_addition = (
                    2.0 * parking_depth / elevator.speed_mps
                    + parking_stops * parking_stop_time
                )
                round_trip_time += parking_round_trip_addition
        interval = normative_interval(round_trip_time, group.elevator_count)
        handling_capacity = group_handling_capacity(
            car_passengers, group.elevator_count, round_trip_time
        )
        specific_capacity = handling_capacity_percent(handling_capacity, population)
        required_percent = float(criteria["traffic_percent_5min_min"])
        required_demand = population * required_percent / 100.0
        user_demand = population * scenario.population_percent_5min / 100.0
        design_demand = max(required_demand, user_demand)
        design_percent = design_demand * 100.0 / population
        full_height_time = travel_height / elevator.speed_mps
        interval_limit = float(criteria["interval_s_max"])
        full_height_min = float(criteria["full_height_time_s_min"])
        full_height_max = float(criteria["full_height_time_s_max"])
        speed_min = nominal_speed_for_travel_time(travel_height, full_height_max)
        speed_max = nominal_speed_for_travel_time(travel_height, full_height_min)
        load_percent = design_demand / handling_capacity * 100.0
        reserve_percent = (handling_capacity - design_demand) / design_demand * 100.0
        average_wait_proxy = interval / 2.0

        kinematic_traces: list[FormulaTrace] = []
        symmetric_profile = include_extended_kinematics and math.isclose(
            elevator.acceleration_mps2,
            elevator.deceleration_mps2,
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
        nominal_plateau_threshold = (
            elevator.acceleration_mps2**2 / elevator.jerk_mps3
        )
        if symmetric_profile and elevator.speed_mps >= nominal_plateau_threshold:
            comparison_sign = "≤" if nominal_speed_reached else ">"
            kinematic_traces.append(
                self._trace(
                    "kinematic_acceleration_distance",
                    (
                        f"sвм = {elevator.speed_mps:.2f}² / "
                        f"(2×{elevator.acceleration_mps2:.2f}) + "
                        f"{elevator.acceleration_mps2:.2f}×{elevator.speed_mps:.2f} / "
                        f"(2×{elevator.jerk_mps3:.2f}) = "
                        f"{nominal_acceleration_distance:.2f}; "
                        f"sвм {comparison_sign} 0.5×dф = "
                        f"{average_floor_height / 2.0:.2f}"
                    ),
                    {
                        "vм": elevator.speed_mps,
                        "a": elevator.acceleration_mps2,
                        "j": elevator.jerk_mps3,
                        "dф": average_floor_height,
                    },
                    {
                        "dф/2": average_floor_height / 2.0,
                        "вывод": (
                            "номинальная скорость достигается"
                            if nominal_speed_reached
                            else "номинальная скорость не достигается"
                        ),
                    },
                    nominal_acceleration_distance,
                    "м",
                )
            )

        peak_plateau_threshold = (
            elevator.acceleration_mps2**2 / elevator.jerk_mps3
        )
        if (
            not nominal_speed_reached
            and symmetric_profile
            and adjacent_floor_peak_speed >= peak_plateau_threshold
        ):
            kinematic_traces.append(
                self._trace(
                    "kinematic_maximum_speed",
                    (
                        f"vм = −{elevator.acceleration_mps2:.2f}² / "
                        f"(2×{elevator.jerk_mps3:.2f}) + √("
                        f"{elevator.acceleration_mps2:.2f}×{average_floor_height:.2f} + "
                        f"({elevator.acceleration_mps2:.2f}² / "
                        f"(2×{elevator.jerk_mps3:.2f}))²) = "
                        f"{adjacent_floor_peak_speed:.2f}"
                    ),
                    {
                        "a": elevator.acceleration_mps2,
                        "j": elevator.jerk_mps3,
                        "dф": average_floor_height,
                    },
                    {"vн": elevator.speed_mps},
                    adjacent_floor_peak_speed,
                    "м/с",
                )
            )

        profile_time_traces = []
        if include_extended_kinematics:
            profile_time_traces.append(
                self._trace(
                    "gost_adjacent_floor_profile_time",
                    (
                        f"tэт = fS(hэт={average_floor_height:.3f}, "
                        f"vн={elevator.speed_mps:.3f}, "
                        f"a={elevator.acceleration_mps2:.3f}, "
                        f"b={elevator.deceleration_mps2:.3f}, "
                        f"j={elevator.jerk_mps3:.3f}) = "
                        f"{floor_motion_phases[0]:.3f} + "
                        f"{floor_motion_phases[1]:.3f} + "
                        f"{floor_motion_phases[2]:.3f} = {floor_profile_time:.3f}"
                    ),
                    {
                        "hэт": average_floor_height,
                        "vн": elevator.speed_mps,
                        "a": elevator.acceleration_mps2,
                        "b": elevator.deceleration_mps2,
                        "j": elevator.jerk_mps3,
                        "tразг": floor_motion_phases[0],
                        "tуст": floor_motion_phases[1],
                        "tторм": floor_motion_phases[2],
                    },
                    {"профиль": "идеальный S-образный, ограниченный a, b и j"},
                    floor_profile_time,
                    "",
                )
            )

        traces = [
            self._trace(
                "gost_nominal_capacity",
                f"Pном = окр₀,₅↑({elevator.capacity_kg:.3f} / 75) = {nominal_capacity}",
                {"Q": elevator.capacity_kg},
                {},
                nominal_capacity,
                "",
            ),
            self._trace(
                "gost_calculated_car_capacity",
                (
                    f"Pк = окр₀,₅↑({nominal_capacity} × "
                    f"{elevator.load_factor:.3f}) = {car_passengers}"
                ),
                {"Pном": nominal_capacity, "kз": elevator.load_factor},
                {"Pном × kз": nominal_capacity * elevator.load_factor},
                car_passengers,
                "",
            ),
            self._trace(
                "gost_passenger_transfer_time",
                (
                    "tв = табл. 3("
                    f"bдвери={elevator.door_width_m * 1000:.0f} мм)"
                ),
                {"bдвери": elevator.door_width_m * 1000.0},
                {},
                transfer_time,
                "",
            ),
            self._trace(
                "gost_probable_stops",
                (
                    f"S = {destination_count} × [1 − (1 − 1/{destination_count})"
                    f"^{car_passengers:.3f}]"
                ),
                {"Nэт": destination_count, "Pк": car_passengers},
                {},
                probable_stops,
                "",
            ),
            self._trace(
                "gost_reversal_floor",
                (
                    f"Nр = {destination_count} − Σ(i/{destination_count})"
                    f"^{car_passengers:.3f}, i=1..{destination_count - 1}"
                ),
                {"Nэт": destination_count, "Pк": car_passengers},
                {},
                reversal_floor,
                "",
            ),
            self._trace(
                "gost_adjacent_floor_time",
                f"tэт.н = {average_floor_height:.3f} / {elevator.speed_mps:.3f}",
                {"hэт": average_floor_height, "vн": elevator.speed_mps},
                {},
                floor_nominal_time,
                "",
            ),
            *kinematic_traces,
            *profile_time_traces,
            self._trace(
                "gost_stop_time",
                (
                    f"tост = {elevator.door_close_time_s:.3f} + "
                    f"{elevator.start_brake_allowance_s:.3f} + {floor_profile_time:.3f} − "
                    f"{elevator.pre_open_time_s:.3f} + {elevator.door_open_time_s:.3f} + "
                    f"{elevator.door_dwell_time_s:.3f} − {floor_nominal_time:.3f}"
                ),
                {
                    "tз": elevator.door_close_time_s,
                    "tз.д": elevator.start_brake_allowance_s,
                    "tэт": floor_profile_time,
                    "tпр": elevator.pre_open_time_s,
                    "tо": elevator.door_open_time_s,
                    "tз.з": elevator.door_dwell_time_s,
                    "tэт.н": floor_nominal_time,
                },
                {},
                stop_time,
                "",
            ),
            self._trace(
                "gost_round_trip_time",
                (
                    f"T = 2×{reversal_floor:.3f}×{floor_nominal_time:.3f} + "
                    f"({probable_stops:.3f}+1)×{stop_time:.3f} + "
                    f"2×{car_passengers:.3f}×{transfer_time:.3f}"
                ),
                {
                    "Nр": reversal_floor,
                    "tэт.н": floor_nominal_time,
                    "S": probable_stops,
                    "tост": stop_time,
                    "Pк": car_passengers,
                    "tв": transfer_time,
                },
                {},
                gost_round_trip_time,
                "",
            ),
            *(
                [
                    self._trace(
                        "parking_lower_reversal",
                        (
                            f"Hм = Σ[1 − (1 − {normative_parking_share:.3f} × "
                            f"(M−k+1)/M)^{car_passengers:.3f}]"
                        ),
                        {
                            "M": len(parking_depths),
                            "Pк": car_passengers,
                            "qм": normative_parking_share,
                        },
                        {},
                        parking_lower_reversal,
                        "",
                    ),
                    self._trace(
                        "parking_expected_depth",
                        "Dм = Σ Δhк × [1 − (1 − qм × (M−k+1)/M)^Pк]",
                        {
                            "M": len(parking_depths),
                            "Pк": car_passengers,
                            "qм": normative_parking_share,
                        },
                        {"глубины": parking_depths},
                        parking_depth,
                        "",
                    ),
                    self._trace(
                        "parking_probable_stops",
                        (
                            f"Sм = {len(parking_depths)} × "
                            f"[1 − (1 − {normative_parking_share:.3f}/"
                            f"{len(parking_depths)})^{car_passengers:.3f}]"
                        ),
                        {
                            "M": len(parking_depths),
                            "Pк": car_passengers,
                            "qм": normative_parking_share,
                        },
                        {},
                        parking_stops,
                        "",
                    ),
                    self._trace(
                        "parking_round_trip_extension",
                        (
                            f"Tм = {gost_round_trip_time:.3f} + "
                            f"2×{parking_depth:.3f}/{elevator.speed_mps:.3f} + "
                            f"{parking_stops:.3f}×{parking_stop_time:.3f}"
                        ),
                        {
                            "TГОСТ": gost_round_trip_time,
                            "Dм": parking_depth,
                            "vн": elevator.speed_mps,
                            "Sм": parking_stops,
                            "tост.м": parking_stop_time,
                        },
                        {"ΔTм": parking_round_trip_addition},
                        round_trip_time,
                        "",
                    ),
                ]
                if parking_extension_active
                else []
            ),
            self._trace(
                "gost_interval",
                f"tи = {round_trip_time:.3f} / {group.elevator_count}",
                {"T": round_trip_time, "Nл": group.elevator_count},
                {},
                interval,
                "",
            ),
            self._trace(
                "gost_group_handling_capacity",
                (
                    f"P5 = 300 × {car_passengers:.3f} × {group.elevator_count} "
                    f"/ {round_trip_time:.3f}"
                ),
                {
                    "Pк": car_passengers,
                    "Nл": group.elevator_count,
                    "T": round_trip_time,
                    "tи": interval,
                },
                {},
                handling_capacity,
                "",
            ),
            self._trace(
                "gost_handling_capacity_percent",
                f"%P5 = {handling_capacity:.3f} × 100 / {population:.3f}",
                {"P5": handling_capacity, "A": population},
                {},
                specific_capacity,
                "",
            ),
            self._trace(
                "gost_nominal_speed",
                f"vн = {travel_height:.3f} / {full_height_max:.3f}",
                {"Hmax": travel_height, "tн": full_height_max},
                {"vн,max": speed_max, "vн,факт": elevator.speed_mps},
                speed_min,
                "",
            ),
        ]

        def status(condition: bool) -> ComplianceStatus:
            return (
                ComplianceStatus.COMPLIES
                if condition
                else ComplianceStatus.DOES_NOT_COMPLY
            )

        parking_metrics = (
            [
                MetricResult(
                    key="parking_share",
                    title_ru="Доля входящего потока с паркинга",
                    value=parking_share * 100.0,
                    unit="%",
                    method="Инженерное расширение (не формула ГОСТ)",
                ),
                MetricResult(
                    key="parking_trip_probability",
                    title_ru="Принятая вероятность заезда на паркинг за рейс",
                    value=parking_trip_probability * 100.0,
                    unit="%",
                    method="Инженерное расширение (не формула ГОСТ)",
                ),
                MetricResult(
                    key="parking_normative_assumption",
                    title_ru="Допущение расчёта по ГОСТ",
                    value=100.0,
                    unit="% рейсов с паркингом",
                    method="Консервативное инженерное допущение",
                ),
                MetricResult(
                    key="parking_lower_reversal",
                    title_ru="Расчётный нижний уровень паркинга",
                    value=parking_lower_reversal,
                    unit="ур.",
                    method="Инженерное расширение (не формула ГОСТ)",
                ),
                MetricResult(
                    key="parking_probable_stops",
                    title_ru="Вероятное число остановок на паркинге",
                    value=parking_stops,
                    unit="ост.",
                    method="Инженерное расширение (не формула ГОСТ)",
                ),
                MetricResult(
                    key="parking_expected_depth",
                    title_ru="Ожидаемая глубина заезда на паркинг",
                    value=parking_depth,
                    unit="м",
                    method="Инженерное расширение (не формула ГОСТ)",
                ),
                MetricResult(
                    key="gost_cycle_time_without_parking",
                    title_ru="Круговой рейс без поправки паркинга",
                    value=gost_round_trip_time,
                    unit="с",
                    method="ГОСТ 34758-2021",
                ),
                MetricResult(
                    key="parking_round_trip_addition",
                    title_ru="Поправка кругового рейса на паркинг",
                    value=parking_round_trip_addition,
                    unit="с",
                    method="Инженерное расширение (не формула ГОСТ)",
                ),
            ]
            if parking_extension_active
            else []
        )

        metrics = [
            MetricResult(
                key="population",
                title_ru="Заселённость обслуживаемой зоны",
                value=population,
                unit="чел.",
                method="ГОСТ 34758-2021",
            ),
            MetricResult(
                key="demand_5min",
                title_ru="Расчётный пассажиропоток за 5 минут",
                value=design_demand,
                unit="пасс./5 мин",
                method="ГОСТ 34758-2021",
                compliance=ComplianceStatus.COMPLIES,
                target_value=required_demand,
                target_description=f"Не менее {required_percent:.1f}% населения",
            ),
            MetricResult(
                key="demand_percent_5min",
                title_ru="Принятый расчётный пассажиропоток",
                value=design_percent,
                unit="% населения/5 мин",
                method="ГОСТ 34758-2021",
                compliance=status(design_percent >= required_percent),
                target_value=required_percent,
                target_description=f"≥ {required_percent:.1f}%",
            ),
            MetricResult(
                key="nominal_capacity",
                title_ru="Номинальная вместимость по грузоподъёмности",
                value=float(nominal_capacity),
                unit="пасс.",
                method="ГОСТ 34758-2021",
            ),
            MetricResult(
                key="actual_car_passengers",
                title_ru="Среднее количество пассажиров в кабине Pк",
                value=car_passengers,
                unit="пасс.",
                method="ГОСТ 34758-2021",
            ),
            MetricResult(
                key="probable_stops",
                title_ru="Вероятное число остановок",
                value=probable_stops,
                unit="ост.",
                method="ГОСТ 34758-2021",
            ),
            MetricResult(
                key="highest_reversal",
                title_ru="Этаж реверса",
                value=reversal_floor,
                unit="эт.",
                method="ГОСТ 34758-2021",
            ),
            MetricResult(
                key="stop_time",
                title_ru="Время, затрачиваемое на остановку",
                value=stop_time,
                unit="с",
                method="ГОСТ 34758-2021",
            ),
            MetricResult(
                key="adjacent_floor_peak_speed",
                title_ru="Максимальная скорость между соседними этажами",
                value=adjacent_floor_peak_speed,
                unit="м/с",
                method=(
                    "Принятая кинематическая интерпретация S-образного профиля"
                    if include_extended_kinematics
                    else "ГОСТ 34758-2021, раздел 7, формула (8)"
                ),
                target_value=elevator.speed_mps,
                target_description=(
                    (
                        "Номинальная скорость достигается"
                        if nominal_speed_reached
                        else "Номинальная скорость на пролёте не достигается"
                    )
                    if include_extended_kinematics
                    else "Принята номинальная скорость по формуле (8)"
                ),
            ),
            MetricResult(
                key="adjacent_floor_profile_time",
                title_ru="Межэтажное время движения с разгоном и торможением",
                value=floor_profile_time,
                unit="с",
                method=(
                    "ГОСТ 34758-2021, принятая кинематическая интерпретация"
                    if include_extended_kinematics
                    else "ГОСТ 34758-2021, раздел 7, формула (8)"
                ),
            ),
            MetricResult(
                key="cycle_time",
                title_ru="Время кругового рейса",
                value=round_trip_time,
                unit="с",
                method=(
                    "ГОСТ 34758-2021 с инженерной поправкой паркинга"
                    if parking_extension_active
                    else "ГОСТ 34758-2021"
                ),
            ),
            *parking_metrics,
            MetricResult(
                key="interval",
                title_ru="Интервал движения лифтов",
                value=interval,
                unit="с",
                method="ГОСТ 34758-2021",
                compliance=status(interval <= interval_limit),
                target_value=interval_limit,
                target_description=f"≤ {interval_limit:.1f} с",
            ),
            MetricResult(
                key="handling_capacity_5min",
                title_ru="Провозная способность группы за 5 минут",
                value=handling_capacity,
                unit="пасс./5 мин",
                method="ГОСТ 34758-2021",
                compliance=status(handling_capacity >= design_demand),
                target_value=design_demand,
                target_description=f"≥ {design_demand:.1f} пасс./5 мин",
            ),
            MetricResult(
                key="specific_capacity",
                title_ru="Провозная способность в процентах от заселённости",
                value=specific_capacity,
                unit="% населения/5 мин",
                method="ГОСТ 34758-2021",
                compliance=status(specific_capacity >= design_percent),
                target_value=design_percent,
                target_description=f"≥ {design_percent:.1f}%",
            ),
            MetricResult(
                key="full_height_time",
                title_ru="Время движения на всю высоту подъёма",
                value=full_height_time,
                unit="с",
                method="ГОСТ 34758-2021",
                # Таблица 4 задаёт рекомендуемый диапазон для выбора скорости,
                # однако более короткое время не ухудшает транспортную комфортность.
                # В приложении Е критерий применяется именно как верхняя граница.
                compliance=status(full_height_time <= full_height_max),
                target_value=full_height_max,
                target_description=f"≤ {full_height_max:.1f} с",
            ),
            MetricResult(
                key="average_wait_proxy",
                title_ru="Ориентировочное время ожидания, не менее",
                value=average_wait_proxy,
                unit="с",
                method="Вспомогательная инженерная оценка",
                compliance=ComplianceStatus.NOT_ASSESSED,
                target_description="Не является критерием расчётного метода ГОСТ",
            ),
            MetricResult(
                key="group_load",
                title_ru="Расчётная загрузка группы",
                value=load_percent,
                unit="%",
                method="ГОСТ 34758-2021",
                compliance=status(load_percent <= 100.0),
                target_value=100.0,
                target_description="≤ 100%",
            ),
            MetricResult(
                key="reserve",
                title_ru="Резерв провозной способности",
                value=reserve_percent,
                unit="%",
                method="ГОСТ 34758-2021",
                compliance=status(reserve_percent >= 0.0),
                target_value=0.0,
                target_description="≥ 0%",
            ),
        ]

        messages = list(validation_messages)
        if include_extended_kinematics and not nominal_speed_reached:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.INFO,
                    code="NOMINAL_SPEED_NOT_REACHED_ADJACENT_FLOOR",
                    text=(
                        f"На среднем межэтажном пролёте {average_floor_height:.2f} м "
                        f"номинальная скорость {elevator.speed_mps:.2f} м/с не "
                        f"достигается. Расчётная максимальная скорость — "
                        f"{adjacent_floor_peak_speed:.2f} м/с; время движения "
                        "рассчитано по S-образному профилю без участка "
                        "установившегося движения."
                    ),
                )
            )
        messages.insert(
            0,
            DiagnosticMessage(
                severity=MessageSeverity.INFO,
                code="GOST_ANALYTIC_METHOD",
                text=(
                    "Выполнен расчётный метод ГОСТ 34758-2021 для пикового "
                    "пассажиропотока вверх: таблицы 1, 3, 4 и формулы (1), (4)–(11)."
                ),
            ),
        )
        messages.append(
            DiagnosticMessage(
                severity=MessageSeverity.WARNING,
                code="SOURCE_AUDIT",
                text=(
                    "Формулы сверены с открытой публикацией и примером приложения Д. "
                    "Перед выпуском договорного отчёта выполните контроль по экземпляру "
                    "стандарта заказчика."
                ),
            )
        )
        if len(project.floors) > 18:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.WARNING,
                    code="MODELING_RECOMMENDED_OVER_18_FLOORS",
                    text=(
                        f"В модели здания {len(project.floors)} этажей. Пункт 5.3 "
                        "ГОСТ 34758-2021 рекомендует для зданий выше 18 этажей "
                        "дополнительно применять метод моделирования. Расчётный метод "
                        "выполнен для выбранной лифтовой группы; результат рекомендуется "
                        "проверить симуляцией."
                    ),
                )
            )
        if parking_extension_active:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.INFO,
                    code="PARKING_ENGINEERING_EXTENSION_APPLIED",
                    text=(
                        f"{scenario.parking_incoming_share:.0%} входящего потока "
                        "задано с парковочных этажей. Для расчёта по ГОСТ принято "
                        "консервативное допущение: каждый круговой рейс включает "
                        "заезд на паркинг. К времени кругового рейса "
                        f"добавлено {parking_round_trip_addition:.2f} с. Это "
                        "инженерное расширение расчётной модели, а не формула ГОСТ; "
                        "результат рекомендуется дополнительно проверить симуляцией."
                    ),
                )
            )
        if user_demand < required_demand:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.INFO,
                    code="DEMAND_RAISED_TO_NORMATIVE_MINIMUM",
                    text=(
                        f"Пользовательский поток {user_demand:.1f} пасс./5 мин повышен "
                        f"до нормативного минимума {required_demand:.1f} пасс./5 мин."
                    ),
                )
            )
        if nominal_capacity != elevator.nominal_passengers:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.WARNING,
                    code="NOMINAL_CAPACITY_RECALCULATED",
                    text=(
                        f"Введённая вместимость {elevator.nominal_passengers} пасс. не совпадает "
                        f"с расчётом Q/75 = {nominal_capacity} пасс.; использовано значение "
                        "по п. 6.5.3."
                    ),
                )
            )
        messages.append(
            DiagnosticMessage(
                severity=MessageSeverity.INFO,
                code="WAIT_PROXY_NOT_NORMATIVE",
                text=(
                    "Показатель I/2 приведён только как вспомогательный; нормативным критерием "
                    "расчётного метода является интервал, а не среднее ожидание."
                ),
            )
        )

        return CalculationResult(
            method=(
                "Расчётный метод ГОСТ 34758-2021 с инженерным учётом паркинга"
                if parking_extension_active
                else "Расчётный метод ГОСТ 34758-2021"
            ),
            calculation_basis="GOST_34758_2021_CLAUSE_7",
            group_id=group.id,
            standard=StandardSelection.GOST_34758_2021.value,
            metrics=metrics,
            formulas=traces,
            messages=messages,
            recommendations=[],
            audit=AuditRecord(
                application_version=__version__,
                configuration_version=self.configuration.configuration_version,
                project_hash=project_hash(project),
            ),
        )

    def calculate_preview(self, project: Project, group_id: str | None = None) -> CalculationResult:
        """Выполняет прозрачную ненормативную оценку пропускной способности группы."""

        validation_messages = ValidationService.validate_project(project)
        blocking = ValidationService.errors(validation_messages)
        if blocking:
            raise ValueError("Расчёт невозможен: " + " ".join(message.text for message in blocking))

        group = project.group(group_id)
        scenario = project.scenario()
        elevator = _average_elevator(group)
        served = [floor for floor in project.floors if floor.number in group.served_floors]
        main_floor = next(
            (floor for floor in served if floor.number == group.main_floor),
            None,
        )
        if main_floor is None:
            raise ValueError("Основной посадочный этаж не найден в зоне обслуживания.")
        parking_floors = [
            floor
            for floor in served
            if floor.number != group.main_floor and floor.is_parking
        ]
        destinations = [
            floor
            for floor in served
            if floor.number != group.main_floor and not floor.is_parking
        ]
        calculation_floors = [main_floor, *destinations]
        population = sum(
            project.effective_floor_population(floor)
            for floor in calculation_floors
        )
        destination_count = len(destinations)
        if destination_count <= 0:
            raise ValueError("Группа должна обслуживать хотя бы один этаж назначения кроме основного.")

        capacity = calculated_capacity(elevator.nominal_passengers, elevator.load_factor)
        probable_stops = probable_stops_uniform(destination_count, capacity)
        reversal_floors = expected_highest_reversal(destination_count, capacity)
        elevations = sorted(floor.elevation_m for floor in calculation_floors)
        floor_steps = [
            right - left for left, right in zip(elevations, elevations[1:], strict=False) if right > left
        ]
        average_floor_height = mean(floor_steps) if floor_steps else mean(floor.floor_height_m for floor in served)
        travel_distance = reversal_floors * average_floor_height
        motion_phases = travel_time_phases(
            travel_distance,
            elevator.speed_mps,
            elevator.acceleration_mps2,
            elevator.deceleration_mps2,
        )
        motion_time = sum(motion_phases)
        stop_time = (
            elevator.door_open_time_s
            + elevator.door_close_time_s
            + elevator.door_dwell_time_s
            + elevator.control_transfer_time_s
            + elevator.leveling_time_s
            + elevator.start_brake_allowance_s
        )
        base_cycle_time = (
            2.0 * motion_time
            + probable_stops * stop_time
            + capacity
            * (elevator.boarding_time_per_passenger_s + elevator.alighting_time_per_passenger_s)
        )
        parking_share = (
            scenario.parking_incoming_share if parking_floors else 0.0
        )
        parking_extension_active = bool(parking_floors and parking_share > 0)
        parking_trip_probability = 0.0
        parking_lower_reversal = 0.0
        parking_stops = 0.0
        parking_depth = 0.0
        parking_motion_time = 0.0
        parking_round_trip_addition = 0.0
        if parking_extension_active:
            parking_depths = sorted(
                main_floor.elevation_m - floor.elevation_m
                for floor in parking_floors
                if floor.elevation_m < main_floor.elevation_m
            )
            if not parking_depths:
                parking_extension_active = False
            else:
                parking_levels = len(parking_depths)
                parking_trip_probability = 1.0 - (
                    1.0 - parking_share
                ) ** capacity
                parking_lower_reversal = expected_parking_lower_reversal(
                    parking_levels,
                    capacity,
                    parking_share,
                )
                parking_stops = probable_parking_stops(
                    parking_levels,
                    capacity,
                    parking_share,
                )
                parking_depth = expected_parking_depth(
                    parking_depths,
                    capacity,
                    parking_share,
                )
                tail_probabilities = [
                    1.0
                    - (
                        1.0
                        - parking_share
                        * (parking_levels - index)
                        / parking_levels
                    )
                    ** capacity
                    for index in range(parking_levels)
                ]
                exact_probabilities = [
                    probability
                    - (
                        tail_probabilities[index + 1]
                        if index + 1 < parking_levels
                        else 0.0
                    )
                    for index, probability in enumerate(tail_probabilities)
                ]
                parking_motion_time = sum(
                    probability
                    * travel_time(
                        depth,
                        elevator.speed_mps,
                        elevator.acceleration_mps2,
                        elevator.deceleration_mps2,
                    )
                    for depth, probability in zip(
                        parking_depths,
                        exact_probabilities,
                        strict=True,
                    )
                )
                parking_round_trip_addition = (
                    2.0 * parking_motion_time + parking_stops * stop_time
                )
        cycle_time = base_cycle_time + parking_round_trip_addition
        interval = cycle_time / group.elevator_count
        handling_capacity = 300.0 * capacity / interval if interval > 0 else 0.0
        specific_capacity = 100.0 * handling_capacity / population if population > 0 else 0.0
        demand = population * scenario.population_percent_5min / 100.0
        average_wait_proxy = interval / 2.0
        load_percent = demand / handling_capacity * 100.0 if handling_capacity > 0 else math.inf
        reserve_percent = (
            (handling_capacity - demand) / demand * 100.0 if demand > 0 else math.inf
        )

        common_warning = (
            "Предварительная инженерная оценка; формула не подтверждена предоставленным "
            "текстом ГОСТ 34758-2021."
        )
        traces = [
            self._trace(
                "calculated_car_capacity",
                (
                    f"C = min({elevator.nominal_passengers}, "
                    f"окр₀,₅↑({elevator.nominal_passengers} × "
                    f"{elevator.load_factor:.3f}))"
                ),
                {"Cном": elevator.nominal_passengers, "kзап": elevator.load_factor},
                {},
                float(capacity),
                common_warning,
            ),
            self._trace(
                "probable_stops_uniform",
                f"S = {destination_count} × (1 - (({destination_count} - 1) / {destination_count})^{capacity})",
                {"N": destination_count, "C": capacity},
                {},
                probable_stops,
                common_warning,
            ),
            self._trace(
                "highest_reversal_uniform",
                f"H = Σ[1 - ((k - 1) / {destination_count})^{capacity}]",
                {"N": destination_count, "C": capacity},
                {"average_floor_height_m": average_floor_height, "travel_distance_m": travel_distance},
                reversal_floors,
                common_warning,
            ),
            self._trace(
                "motion_time",
                (
                    f"tдв = f(d={travel_distance:.3f}, v={elevator.speed_mps:.3f}, "
                    f"a={elevator.acceleration_mps2:.3f}, "
                    f"b={elevator.deceleration_mps2:.3f}) = "
                    f"{motion_phases[0]:.3f} + {motion_phases[1]:.3f} + "
                    f"{motion_phases[2]:.3f} = {motion_time:.3f}"
                ),
                {
                    "d": travel_distance,
                    "v": elevator.speed_mps,
                    "a": elevator.acceleration_mps2,
                    "b": elevator.deceleration_mps2,
                    "tразг": motion_phases[0],
                    "tуст": motion_phases[1],
                    "tторм": motion_phases[2],
                },
                {},
                motion_time,
                "Общая кинематика; рывок в текущей версии не интегрируется в профиль движения.",
            ),
            self._trace(
                "engineering_cycle_time",
                (
                    f"Tцикл = 2×{motion_time:.3f} + "
                    f"{probable_stops:.3f}×{stop_time:.3f} + "
                    f"{capacity}×({elevator.boarding_time_per_passenger_s:.3f} + "
                    f"{elevator.alighting_time_per_passenger_s:.3f}) + "
                    f"{parking_round_trip_addition:.3f}"
                ),
                {
                    "tдв": motion_time,
                    "S": probable_stops,
                    "tост": stop_time,
                    "C": capacity,
                    "tпос": elevator.boarding_time_per_passenger_s,
                    "tвыс": elevator.alighting_time_per_passenger_s,
                },
                {},
                cycle_time,
                common_warning,
            ),
            self._trace(
                "interval",
                f"I = {cycle_time:.3f} / {group.elevator_count}",
                {"Tцикл": cycle_time, "L": group.elevator_count},
                {},
                interval,
                common_warning,
            ),
            self._trace(
                "handling_capacity_5min",
                f"HC5 = 300 × {capacity} / {interval:.3f}",
                {"C": capacity, "I": interval},
                {},
                handling_capacity,
                common_warning,
            ),
            self._trace(
                "average_wait_proxy",
                f"tож,ор = {interval:.3f} / 2",
                {"I": interval},
                {},
                average_wait_proxy,
                common_warning,
            ),
        ]

        metric_values = [
            ("population", "Население, обслуживаемое группой", population, "чел."),
            ("demand_5min", "Расчётный пассажиропоток за 5 минут", demand, "пасс./5 мин"),
            ("calculated_capacity", "Расчётная вместимость кабины", capacity, "пасс."),
            ("actual_car_passengers", "Принятое число пассажиров в кабине", capacity, "пасс."),
            ("probable_stops", "Ожидаемое число остановок", probable_stops, "ост."),
            ("highest_reversal", "Ожидаемый наивысший этаж разворота", reversal_floors, "эт."),
            ("average_trip_height", "Оценочная высота поездки", travel_distance, "м"),
            ("motion_time", "Время движения до этажа разворота", motion_time, "с"),
            ("cycle_time", "Предварительное время цикла (не нормативный RTT)", cycle_time, "с"),
            ("interval", "Предварительный интервал", interval, "с"),
            ("handling_capacity_5min", "Провозная способность за 5 минут", handling_capacity, "пасс./5 мин"),
            ("specific_capacity", "Удельная провозная способность", specific_capacity, "% населения/5 мин"),
            (
                "average_wait_proxy",
                "Ориентировочное время ожидания, не менее",
                average_wait_proxy,
                "с",
            ),
            ("group_load", "Расчётная загрузка группы", load_percent, "%"),
            ("reserve", "Резерв относительно заданного потока", reserve_percent, "%"),
        ]
        if parking_extension_active:
            metric_values.extend(
                [
                    (
                        "parking_share",
                        "Фактическая доля входящего потока с паркинга",
                        parking_share * 100.0,
                        "%",
                    ),
                    (
                        "parking_trip_probability",
                        "Вероятность заезда на паркинг за рейс",
                        parking_trip_probability * 100.0,
                        "%",
                    ),
                    (
                        "parking_lower_reversal",
                        "Ожидаемый нижний уровень паркинга",
                        parking_lower_reversal,
                        "ур.",
                    ),
                    (
                        "parking_probable_stops",
                        "Ожидаемое число остановок на паркинге",
                        parking_stops,
                        "ост.",
                    ),
                    (
                        "parking_expected_depth",
                        "Ожидаемая глубина заезда на паркинг",
                        parking_depth,
                        "м",
                    ),
                    (
                        "parking_round_trip_addition",
                        "Добавка времени цикла из-за паркинга",
                        parking_round_trip_addition,
                        "с",
                    ),
                ]
            )
        metrics = [
            MetricResult(
                key=key,
                title_ru=title,
                value=float(value),
                unit=unit,
                method="Предварительный инженерный расчёт",
                compliance=ComplianceStatus.NOT_ASSESSED,
                target_description="Нормативный критерий не загружен",
            )
            for key, title, value, unit in metric_values
        ]
        messages = list(validation_messages)
        messages.insert(
            0,
            DiagnosticMessage(
                severity=MessageSeverity.WARNING,
                code="NORMATIVE_NOT_ASSESSED",
                text=(
                    "Нормативное соответствие не оценено: отсутствуют предоставленные и "
                    "верифицированные формулы, критерии и пункты стандартов."
                ),
            ),
        )
        if parking_floors and scenario.parking_incoming_share > 0:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.INFO,
                    code="PARKING_EXACT_SHARE_APPLIED",
                    text=(
                        f"{scenario.parking_incoming_share:.0%} входящего потока "
                        "начинается на парковочных этажах. Предварительный расчёт "
                        "учитывает эту фактическую долю; симуляция использует её "
                        "непосредственно при генерации поездок."
                    ),
                )
            )
        return CalculationResult(
            method="Предварительный инженерный расчёт",
            calculation_basis="ENGINEERING_PREVIEW",
            group_id=group.id,
            standard=project.metadata.selected_standard.value,
            metrics=metrics,
            formulas=traces,
            messages=messages,
            recommendations=[],
            audit=AuditRecord(
                application_version=__version__,
                configuration_version=self.configuration.configuration_version,
                project_hash=project_hash(project),
            ),
        )

    def _trace(
        self,
        formula_id: str,
        substituted_expression: str,
        variables: dict[str, float | int],
        intermediate_values: dict[str, float],
        result: float,
        warning: str,
    ) -> FormulaTrace:
        item = self.formulas.get(formula_id)
        return FormulaTrace(
            formula_id=formula_id,
            title_ru=item["title_ru"],
            expression=item["expression"],
            substituted_expression=substituted_expression,
            variables=variables,
            intermediate_values=intermediate_values,
            result=float(result),
            unit=item["unit"],
            standard=item["standard"],
            clause=item.get("clause"),
            status=item["status"],
            warnings=[warning] if warning else [],
        )
