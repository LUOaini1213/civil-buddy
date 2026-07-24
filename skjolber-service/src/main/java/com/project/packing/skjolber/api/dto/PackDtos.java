package com.project.packing.skjolber.api.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class PackDtos {

    private PackDtos() {}

    public record PackRequest(
            String requestId,
            @Valid @NotNull PlanDto plan,
            @NotEmpty List<@Valid BoxDto> boxes,
            List<@Valid ContainerSpecDto> containerCatalog
    ) {}

    public record PlanDto(
            String strategy,
            String priority,
            Integer maxContainers,
            List<String> preferredContainerTypes,
            Boolean allowRotation,
            Map<String, Object> constraints,
            Long timeoutMs,
            List<String> special_rules,
            String container_type,
            List<String> priority_order
    ) {}

    public record BoxDto(
            @NotBlank String box_id,
            String box_type,
            @Valid OuterSize outer_size_mm,
            Double gross_weight_kg,
            Double net_weight_kg,
            List<String> special_attributes,
            Boolean allowRotate,
            Boolean stackable
    ) {}

    public record OuterSize(
            @NotNull Double length,
            @NotNull Double width,
            @NotNull Double height
    ) {}

    public record ContainerSpecDto(
            @NotBlank String type,
            int lengthMm,
            int widthMm,
            int heightMm,
            double emptyWeightKg,
            double maxLoadWeightKg
    ) {}

    public record PackResponse(
            String requestId,
            boolean success,
            String algorithm,
            long durationMs,
            int containersUsed,
            List<String> unpackedBoxIds,
            ContainerPlanDto container_plan,
            String message,
            String engine
    ) {}

    public record ContainerPlanDto(
            String container_type,
            int containers_used,
            double space_utilization,
            double weight_utilization,
            boolean can_fit,
            List<PlacementDto> layout,
            List<String> unpacked_box_ids,
            String message,
            String engine
    ) {}

    public record PlacementDto(
            String box_id,
            int container_no,
            PositionDto position,
            SizeDto size,
            String rotation,
            int layer
    ) {}

    public record PositionDto(int x, int y, int z) {}

    public record SizeDto(int dx, int dy, int dz) {}

    public static List<ContainerSpecDto> defaultCatalog() {
        List<ContainerSpecDto> list = new ArrayList<>();
        list.add(new ContainerSpecDto("20GP", 5898, 2352, 2393, 2200, 21770));
        list.add(new ContainerSpecDto("40GP", 12032, 2352, 2393, 3800, 26680));
        list.add(new ContainerSpecDto("40HQ", 12032, 2352, 2698, 3900, 26480));
        list.add(new ContainerSpecDto("45HQ", 13556, 2352, 2698, 4800, 27700));
        return list;
    }
}
