"""Детерминированная дискретно-событийная модель пассажиропотока."""

from __future__ import annotations

import heapq
import itertools
from collections import defaultdict, deque
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

import numpy as np

from src.controllers.collective_control import choose_collective_car
from src.models.elevator import Elevator, ElevatorGroup
from src.models.project import Project
from src.models.simulation import (
    ElevatorTrajectoryPoint,
    Passenger,
    SimulationResult,
    SimulationSettings,
)
from src.models.traffic import ArrivalDistribution, TrafficScenario
from src.services.validation_service import ValidationService
from src.utils.hashing import project_hash
from src.utils.statistics import describe

from .analytic_engine import calculated_capacity, travel_time


@dataclass
class _ElevatorState:
    index: int
    elevator: Elevator
    current_floor: int
    idle: bool = True
    planned_destinations: list[int] = field(default_factory=list)
    busy_time_s: float = 0.0
    distance_floors: float = 0.0


@dataclass
class _RunResult:
    passengers: list[Passenger]
    queue_series: list[dict[str, float]]
    trajectories: list[ElevatorTrajectoryPoint]
    average_queue: float
    maximum_queue: int
    loads: list[int]
    stops_count: int
    idle_runs: int
    car_distance: dict[str, float]
    utilization: dict[str, float]


class SimulationEngine:
    """Моделирует поступление, очередь, назначение, движение, двери и вместимость."""

    def run(
        self,
        project: Project,
        settings: SimulationSettings,
        group_id: str | None = None,
    ) -> SimulationResult:
        """Выполняет независимые повторы и агрегирует пассажирские показатели."""

        messages = ValidationService.validate_project(project)
        errors = ValidationService.errors(messages)
        if errors:
            raise ValueError("Симуляция невозможна: " + " ".join(item.text for item in errors))
        group = project.group(group_id)
        scenario = project.scenario().model_copy(update={"duration_s": settings.duration_s})
        all_waits: list[float] = []
        all_ttd: list[float] = []
        journey_times: list[float] = []
        run_queue_averages: list[float] = []
        run_max_queues: list[int] = []
        run_transported: list[int] = []
        run_unserved: list[int] = []
        run_average_loads: list[float] = []
        run_max_loads: list[int] = []
        run_stops: list[int] = []
        run_idle_runs: list[int] = []
        detailed: _RunResult | None = None
        distance_accumulator: dict[str, list[float]] = defaultdict(list)
        utilization_accumulator: dict[str, list[float]] = defaultdict(list)

        for repetition in range(settings.repetitions):
            rng = np.random.default_rng(settings.random_seed + repetition)
            passengers = self.generate_passengers(project, scenario, rng, group)
            run = self._run_once(project, group, passengers, settings, rng)
            if repetition == 0:
                detailed = run
            measured = [
                passenger
                for passenger in run.passengers
                if passenger.arrival_time_s >= settings.warmup_s
            ]
            served = [passenger for passenger in measured if passenger.status == "served"]
            waits = [float(passenger.waiting_time_s or 0.0) for passenger in served]
            ttd = [float(passenger.time_to_destination_s or 0.0) for passenger in served]
            journeys = [float(passenger.journey_time_s or 0.0) for passenger in served]
            all_waits.extend(waits)
            all_ttd.extend(ttd)
            journey_times.extend(journeys)
            run_queue_averages.append(run.average_queue)
            run_max_queues.append(run.maximum_queue)
            run_transported.append(len(served))
            run_unserved.append(len(measured) - len(served))
            run_average_loads.append(mean(run.loads) if run.loads else 0.0)
            run_max_loads.append(max(run.loads, default=0))
            run_stops.append(run.stops_count)
            run_idle_runs.append(run.idle_runs)
            for elevator_id, distance in run.car_distance.items():
                distance_accumulator[elevator_id].append(distance)
            for elevator_id, utilization in run.utilization.items():
                utilization_accumulator[elevator_id].append(utilization)

        assert detailed is not None
        return SimulationResult(
            group_id=group.id,
            seed=settings.random_seed,
            repetitions=settings.repetitions,
            waiting_time=describe(all_waits),
            time_to_destination=describe(all_ttd),
            average_journey_time_s=mean(journey_times) if journey_times else 0.0,
            maximum_waiting_time_s=max(all_waits, default=0.0),
            average_queue_length=mean(run_queue_averages) if run_queue_averages else 0.0,
            maximum_queue_length=max(run_max_queues, default=0),
            transported_passengers=round(mean(run_transported)) if run_transported else 0,
            unserved_passengers=round(mean(run_unserved)) if run_unserved else 0,
            average_car_load=mean(run_average_loads) if run_average_loads else 0.0,
            maximum_car_load=max(run_max_loads, default=0),
            stops_count=round(mean(run_stops)) if run_stops else 0,
            idle_runs=round(mean(run_idle_runs)) if run_idle_runs else 0,
            car_distance_floors={
                elevator_id: mean(values) for elevator_id, values in distance_accumulator.items()
            },
            utilization={
                elevator_id: mean(values) for elevator_id, values in utilization_accumulator.items()
            },
            passengers=detailed.passengers,
            queue_time_series=detailed.queue_series,
            trajectories=detailed.trajectories,
            warnings=[
                "MVP использует назначение ближайшей свободной кабины и пакетную посадку с одного этажа.",
                "Базовая эвристика не идентична промышленным алгоритмам Destination Control.",
                "Энергопотребление не рассчитывается: подтверждённая модель не предоставлена.",
            ],
            project_hash=project_hash(project),
        )

    def generate_passengers(
        self,
        project: Project,
        scenario: TrafficScenario,
        rng: np.random.Generator,
        group: ElevatorGroup | None = None,
    ) -> list[Passenger]:
        """Генерирует пассажиров по распределению и направлению сценария."""

        if scenario.arrival_distribution == ArrivalDistribution.IMPORTED and scenario.imported_passengers:
            rows = sorted(scenario.imported_passengers, key=lambda item: float(item["arrival_time_s"]))
            return [
                Passenger(
                    id=index,
                    arrival_time_s=float(row["arrival_time_s"]),
                    origin_floor=int(row["origin_floor"]),
                    destination_floor=int(row["destination_floor"]),
                    wait_start_time_s=float(row["arrival_time_s"]),
                )
                for index, row in enumerate(rows, start=1)
                if int(row["origin_floor"]) != int(row["destination_floor"])
            ]

        population = project.population
        expected_5min = population * scenario.population_percent_5min / 100.0
        expected_total = expected_5min * scenario.duration_s / 300.0
        times = self._arrival_times(scenario, expected_total, rng)
        active_group = group or project.group()
        floors = [floor for floor in project.floors if floor.number in active_group.served_floors]
        if len(floors) < 2:
            raise ValueError("Для генерации поездок требуется не менее двух обслуживаемых этажей.")
        main_floor = active_group.main_floor
        passenger_floors = [
            floor
            for floor in floors
            if floor.number != main_floor and not floor.is_parking and floor.population > 0
        ]
        parking_floors = [
            floor
            for floor in floors
            if floor.number != main_floor and floor.is_parking
        ]
        if not passenger_floors:
            raise ValueError(
                "Для генерации поездок требуется хотя бы один населённый этаж "
                "кроме основного и парковочных этажей."
            )
        weights = np.asarray(
            [max(0, floor.population) for floor in passenger_floors],
            dtype=float,
        )
        if weights.sum() <= 0:
            weights = np.ones(len(passenger_floors), dtype=float)
        weights = weights / weights.sum()

        passengers: list[Passenger] = []
        for index, arrival_time in enumerate(times, start=1):
            origin, destination = self._choose_od(
                scenario,
                main_floor,
                passenger_floors,
                parking_floors,
                weights,
                rng,
            )
            passengers.append(
                Passenger(
                    id=index,
                    arrival_time_s=float(arrival_time),
                    origin_floor=origin,
                    destination_floor=destination,
                    wait_start_time_s=float(arrival_time),
                )
            )
        return passengers

    @staticmethod
    def _arrival_times(
        scenario: TrafficScenario,
        expected_total: float,
        rng: np.random.Generator,
    ) -> np.ndarray:
        if expected_total <= 0:
            return np.asarray([], dtype=float)
        if scenario.arrival_distribution == ArrivalDistribution.DETERMINISTIC:
            count = max(1, round(expected_total))
            return np.linspace(0, scenario.duration_s, count, endpoint=False) + scenario.duration_s / (2 * count)
        if scenario.arrival_distribution == ArrivalDistribution.BATCH:
            count = max(1, round(expected_total))
            batch_size = 3
            batch_count = max(1, int(np.ceil(count / batch_size)))
            batch_times = np.linspace(0, scenario.duration_s, batch_count, endpoint=False)
            return np.sort(np.repeat(batch_times, batch_size)[:count])
        if (
            scenario.arrival_distribution
            in {ArrivalDistribution.NONSTATIONARY_POISSON, ArrivalDistribution.PROFILE}
            and scenario.intensity_profile
        ):
            profile = np.asarray(scenario.intensity_profile, dtype=float)
            profile = np.clip(profile, 0, None)
            if profile.sum() <= 0:
                return np.asarray([], dtype=float)
            profile = profile / profile.sum()
            edges = np.linspace(0, scenario.duration_s, profile.size + 1)
            generated: list[float] = []
            for index, share in enumerate(profile):
                count = int(rng.poisson(expected_total * share))
                generated.extend(rng.uniform(edges[index], edges[index + 1], count))
            return np.sort(np.asarray(generated, dtype=float))
        count = int(rng.poisson(expected_total))
        if scenario.random_bursts and count > 0:
            count += int(rng.poisson(max(1.0, expected_total * 0.1)))
        return np.sort(rng.uniform(0, scenario.duration_s, count))

    @staticmethod
    def _choose_od(
        scenario: TrafficScenario,
        main_floor: int,
        passenger_floors: list[Any],
        parking_floors: list[Any],
        weights: np.ndarray,
        rng: np.random.Generator,
    ) -> tuple[int, int]:
        movement = str(
            rng.choice(
                ["incoming", "outgoing", "interfloor"],
                p=[scenario.incoming_share, scenario.outgoing_share, scenario.interfloor_share],
            )
        )
        if movement == "incoming":
            destination = int(
                rng.choice([floor.number for floor in passenger_floors], p=weights)
            )
            if (
                parking_floors
                and scenario.parking_incoming_share > 0
                and rng.random() < scenario.parking_incoming_share
            ):
                origin = int(
                    rng.choice([floor.number for floor in parking_floors])
                )
                return origin, destination
            return main_floor, destination
        if movement == "outgoing":
            origin = int(
                rng.choice([floor.number for floor in passenger_floors], p=weights)
            )
            return origin, main_floor
        origin = int(
            rng.choice([floor.number for floor in passenger_floors], p=weights)
        )
        destinations = [
            floor.number for floor in passenger_floors if floor.number != origin
        ]
        if not destinations:
            return origin, main_floor
        destination = int(rng.choice(destinations))
        return origin, destination

    def _run_once(
        self,
        project: Project,
        group: ElevatorGroup,
        passengers: list[Passenger],
        settings: SimulationSettings,
        rng: np.random.Generator,
    ) -> _RunResult:
        elevations = {floor.number: floor.elevation_m for floor in project.floors}
        average_height = mean(floor.floor_height_m for floor in project.floors)
        states = [
            _ElevatorState(index=index, elevator=elevator, current_floor=group.main_floor)
            for index, elevator in enumerate(group.elevators)
        ]
        waiting: dict[int, deque[int]] = defaultdict(deque)
        passenger_by_id = {passenger.id: passenger for passenger in passengers}
        events: list[tuple[float, int, str, dict[str, Any]]] = []
        sequence = itertools.count()
        queue_series: list[dict[str, float]] = [{"time_s": 0.0, "queue_length": 0.0}]
        trajectories: list[ElevatorTrajectoryPoint] = []
        loads: list[int] = []
        stops_count = 0
        idle_runs = 0
        maximum_queue = 0

        def push(time_s: float, event_type: str, payload: dict[str, Any]) -> None:
            heapq.heappush(events, (time_s, next(sequence), event_type, payload))

        def queue_length() -> int:
            return sum(len(queue) for queue in waiting.values())

        def record_queue(time_s: float) -> None:
            nonlocal maximum_queue
            current = queue_length()
            maximum_queue = max(maximum_queue, current)
            queue_series.append({"time_s": float(time_s), "queue_length": float(current)})

        def distance_m(origin: int, destination: int) -> float:
            if origin in elevations and destination in elevations:
                return abs(elevations[destination] - elevations[origin])
            return abs(destination - origin) * average_height

        def movement_time(elevator: Elevator, origin: int, destination: int) -> float:
            return travel_time(
                distance_m(origin, destination),
                elevator.speed_mps,
                elevator.acceleration_mps2,
                elevator.deceleration_mps2,
            )

        def dispatch(time_s: float) -> None:
            while any(state.idle for state in states) and any(waiting.values()):
                candidates = [
                    (passenger_by_id[queue[0]].arrival_time_s, origin)
                    for origin, queue in waiting.items()
                    if queue
                ]
                if not candidates:
                    return
                _, origin = min(candidates, key=lambda item: (item[0], item[1]))
                elevator_index = choose_collective_car(states, origin)
                state = states[elevator_index]
                state.idle = False
                move = movement_time(state.elevator, state.current_floor, origin)
                if state.current_floor == origin:
                    nonlocal idle_runs
                    idle_runs += 1
                state.busy_time_s += move
                state.distance_floors += abs(state.current_floor - origin)
                trajectories.append(
                    ElevatorTrajectoryPoint(
                        elevator_id=state.elevator.id,
                        time_s=time_s,
                        floor=state.current_floor,
                        event="dispatch",
                    )
                )
                push(time_s + move, "pickup", {"elevator_index": elevator_index, "origin": origin})

        for passenger in passengers:
            push(passenger.arrival_time_s, "arrival", {"passenger_id": passenger.id})

        last_time = 0.0
        while events:
            time_s, _, event_type, payload = heapq.heappop(events)
            last_time = max(last_time, time_s)
            if event_type == "arrival":
                passenger = passenger_by_id[payload["passenger_id"]]
                if queue_length() >= settings.maximum_queue_length:
                    passenger.status = "unserved_queue_limit"
                else:
                    waiting[passenger.origin_floor].append(passenger.id)
                record_queue(time_s)
                dispatch(time_s)
                continue

            elevator_index = int(payload["elevator_index"])
            state = states[elevator_index]
            elevator = state.elevator
            if event_type == "available":
                state.idle = True
                state.planned_destinations = []
                dispatch(time_s)
                continue

            origin = int(payload["origin"])
            queue = waiting[origin]
            capacity = calculated_capacity(elevator.nominal_passengers, elevator.load_factor)
            boarded: list[Passenger] = []
            retained: deque[int] = deque()
            while queue:
                passenger = passenger_by_id[queue.popleft()]
                waited = time_s - passenger.arrival_time_s
                if (
                    waited > settings.maximum_wait_s
                    and settings.abandon_probability > 0
                    and rng.random() < settings.abandon_probability
                ):
                    passenger.status = "abandoned"
                    passenger.waiting_time_s = waited
                    continue
                if len(boarded) < capacity:
                    boarded.append(passenger)
                else:
                    retained.append(passenger.id)
            waiting[origin] = retained
            record_queue(time_s)
            if not boarded:
                state.current_floor = origin
                push(time_s, "available", {"elevator_index": elevator_index})
                continue

            loads.append(len(boarded))
            boarding_multiplier = 1.0 + settings.slow_boarding_share
            pickup_service = (
                elevator.door_open_time_s
                + elevator.door_dwell_time_s
                + len(boarded) * elevator.boarding_time_per_passenger_s * boarding_multiplier
                + elevator.door_close_time_s
            )
            for passenger in boarded:
                passenger.board_time_s = time_s + elevator.door_open_time_s
                passenger.waiting_time_s = passenger.board_time_s - passenger.arrival_time_s
                passenger.status = "onboard"
                passenger.elevator_id = elevator.id

            destinations = sorted(
                {passenger.destination_floor for passenger in boarded},
                reverse=boarded[0].destination_floor < origin,
            )
            state.planned_destinations = list(destinations)
            current_floor = origin
            current_time = time_s + pickup_service
            state.busy_time_s += pickup_service
            trajectories.append(
                ElevatorTrajectoryPoint(
                    elevator_id=elevator.id,
                    time_s=time_s,
                    floor=origin,
                    event="pickup",
                )
            )
            for destination in destinations:
                move = movement_time(elevator, current_floor, destination)
                current_time += move + elevator.leveling_time_s
                state.busy_time_s += move + elevator.leveling_time_s
                state.distance_floors += abs(destination - current_floor)
                alighting = [passenger for passenger in boarded if passenger.destination_floor == destination]
                door_service = (
                    elevator.door_open_time_s
                    + len(alighting) * elevator.alighting_time_per_passenger_s
                    + elevator.door_dwell_time_s
                    + elevator.door_close_time_s
                )
                for passenger in alighting:
                    passenger.exit_time_s = current_time + elevator.door_open_time_s
                    passenger.journey_time_s = passenger.exit_time_s - float(passenger.board_time_s)
                    passenger.time_to_destination_s = passenger.exit_time_s - passenger.arrival_time_s
                    passenger.status = "served"
                trajectories.append(
                    ElevatorTrajectoryPoint(
                        elevator_id=elevator.id,
                        time_s=current_time,
                        floor=destination,
                        event="dropoff",
                    )
                )
                current_time += door_service
                state.busy_time_s += door_service
                current_floor = destination
                stops_count += 1
            state.current_floor = current_floor
            push(current_time, "available", {"elevator_index": elevator_index})
            dispatch(time_s)

        for passenger in passengers:
            if passenger.status == "waiting":
                passenger.status = "unserved"
        queue_values = [point["queue_length"] for point in queue_series]
        return _RunResult(
            passengers=passengers,
            queue_series=queue_series,
            trajectories=trajectories,
            average_queue=mean(queue_values) if queue_values else 0.0,
            maximum_queue=maximum_queue,
            loads=loads,
            stops_count=stops_count,
            idle_runs=idle_runs,
            car_distance={state.elevator.id: state.distance_floors for state in states},
            utilization={
                state.elevator.id: min(1.0, state.busy_time_s / max(settings.duration_s, last_time, 1.0))
                for state in states
            },
        )
