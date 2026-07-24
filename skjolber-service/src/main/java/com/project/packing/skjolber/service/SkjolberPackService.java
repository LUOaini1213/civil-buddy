package com.project.packing.skjolber.service;

import com.github.skjolber.packing.api.Box;
import com.github.skjolber.packing.api.Container;
import com.github.skjolber.packing.api.StackPlacement;
import com.github.skjolber.packing.api.StackableItem;
import com.github.skjolber.packing.packer.Packager;
import com.github.skjolber.packing.packer.bruteforce.BruteForcePackager;
import com.github.skjolber.packing.packer.laff.LargestAreaFitFirstPackager;
import com.github.skjolber.packing.packer.plain.PlainPackager;
import com.project.packing.skjolber.api.dto.PackDtos;
import com.project.packing.skjolber.api.dto.PackDtos.BoxDto;
import com.project.packing.skjolber.api.dto.PackDtos.ContainerPlanDto;
import com.project.packing.skjolber.api.dto.PackDtos.ContainerSpecDto;
import com.project.packing.skjolber.api.dto.PackDtos.PackRequest;
import com.project.packing.skjolber.api.dto.PackDtos.PackResponse;
import com.project.packing.skjolber.api.dto.PackDtos.PlacementDto;
import com.project.packing.skjolber.api.dto.PackDtos.PlanDto;
import com.project.packing.skjolber.api.dto.PackDtos.PositionDto;
import com.project.packing.skjolber.api.dto.PackDtos.SizeDto;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * skjolber 3.x 封装。
 * 若编译报 API 差异，请对照本地 core jar 微调 import/方法名。
 */
@Service
public class SkjolberPackService {

    @Value("${packing.default-timeout-ms:8000}")
    private long defaultTimeoutMs;

    public PackResponse pack(PackRequest request) {
        long t0 = System.currentTimeMillis();
        PlanDto plan = request.plan();
        String strategy = resolveStrategy(plan);
        Packager<Container> packager = createPackager(strategy);

        List<BoxDto> boxes = new ArrayList<>(request.boxes());
        sortBoxes(boxes, plan);

        List<StackableItem> products = new ArrayList<>();
        Map<String, BoxDto> boxMap = new HashMap<>();
        for (BoxDto b : boxes) {
            products.add(toStackableItem(b, plan));
            boxMap.put(b.box_id(), b);
        }

        List<ContainerSpecDto> catalog = request.containerCatalog();
        if (catalog == null || catalog.isEmpty()) {
            catalog = PackDtos.defaultCatalog();
        }
        String preferredType = resolveContainerType(plan);
        int maxContainers = plan.maxContainers() == null || plan.maxContainers() < 1
                ? 1 : plan.maxContainers();

        List<Container> containers = new ArrayList<>();
        Map<String, ContainerSpecDto> specByType = new HashMap<>();
        for (ContainerSpecDto spec : orderCatalog(catalog, preferredType)) {
            specByType.put(spec.type(), spec);
            for (int i = 0; i < maxContainers; i++) {
                containers.add(toContainer(spec, i + 1));
            }
        }

        List<Container> matches;
        try {
            // 3.x: pack(List<StackableItem>, List<Container>)
            matches = packager.pack(products, containers);
        } catch (Exception e1) {
            try {
                // 部分版本签名不同
                matches = packager.pack(products, containers, System.currentTimeMillis() + defaultTimeoutMs);
            } catch (Exception e2) {
                long duration = System.currentTimeMillis() - t0;
                return fail(request.requestId(), strategy, duration,
                        "skjolber pack failed: " + e2.getMessage(), boxes);
            }
        }

        long duration = System.currentTimeMillis() - t0;
        return mapMatches(request.requestId(), strategy, matches, boxes, boxMap, preferredType, catalog, duration);
    }

    private PackResponse fail(String requestId, String strategy, long duration, String msg, List<BoxDto> boxes) {
        List<String> all = boxes.stream().map(BoxDto::box_id).toList();
        ContainerPlanDto planDto = new ContainerPlanDto(
                "40HQ", 0, 0, 0, false, List.of(), all, msg, "skjolber-error");
        return new PackResponse(requestId, false, strategy, duration, 0, all, planDto, msg, "skjolber-error");
    }

    private String resolveStrategy(PlanDto plan) {
        if (plan == null || plan.strategy() == null || plan.strategy().isBlank()) {
            return "LARGEST_AREA_FIT_FIRST";
        }
        String s = plan.strategy().toUpperCase(Locale.ROOT);
        if (s.contains("BRUTE")) {
            return "BRUTE_FORCE";
        }
        if (s.contains("PLAIN")) {
            return "PLAIN";
        }
        return "LARGEST_AREA_FIT_FIRST";
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private Packager<Container> createPackager(String strategy) {
        return switch (strategy) {
            case "BRUTE_FORCE" -> (Packager) BruteForcePackager.newBuilder().build();
            case "PLAIN" -> (Packager) PlainPackager.newBuilder().build();
            default -> (Packager) LargestAreaFitFirstPackager.newBuilder().build();
        };
    }

    private String resolveContainerType(PlanDto plan) {
        if (plan == null) {
            return "40HQ";
        }
        if (plan.container_type() != null && !plan.container_type().isBlank()) {
            return plan.container_type();
        }
        if (plan.preferredContainerTypes() != null && !plan.preferredContainerTypes().isEmpty()) {
            return plan.preferredContainerTypes().get(0);
        }
        return "40HQ";
    }

    private void sortBoxes(List<BoxDto> boxes, PlanDto plan) {
        if (plan != null && plan.priority_order() != null && !plan.priority_order().isEmpty()) {
            List<String> order = plan.priority_order();
            boxes.sort(Comparator.comparingInt(b -> {
                int i = order.indexOf(b.box_id());
                return i < 0 ? 999 : i;
            }));
            return;
        }
        boxes.sort((a, b) -> Double.compare(
                b.outer_size_mm().length(),
                a.outer_size_mm().length()));
    }

    private StackableItem toStackableItem(BoxDto b, PlanDto plan) {
        int dx = Math.max(1, (int) Math.round(b.outer_size_mm().length()));
        int dy = Math.max(1, (int) Math.round(b.outer_size_mm().width()));
        int dz = Math.max(1, (int) Math.round(b.outer_size_mm().height()));
        int weight = Math.max(1, (int) Math.round(
                b.gross_weight_kg() != null ? b.gross_weight_kg() : 1));

        boolean allowRotate = b.allowRotate() == null || Boolean.TRUE.equals(b.allowRotate());
        if (plan != null && Boolean.FALSE.equals(plan.allowRotation())) {
            allowRotate = false;
        }
        List<String> special = b.special_attributes() == null ? List.of() : b.special_attributes();
        if (special.stream().anyMatch(s -> s != null && s.contains("超长")) || dx >= 5800) {
            allowRotate = false;
        }

        Box.Builder builder = Box.newBuilder()
                .withId(b.box_id())
                .withSize(dx, dy, dz)
                .withWeight(weight);
        if (allowRotate) {
            builder.withRotate3D();
        } else {
            // 仅允许水平面旋转（若 API 支持）；否则固定朝向
            try {
                builder.withRotate2D();
            } catch (Throwable ignored) {
                // keep fixed orientation
            }
        }
        return new StackableItem(builder.build(), 1);
    }

    private Container toContainer(ContainerSpecDto spec, int index) {
        return Container.newBuilder()
                .withDescription(spec.type() + "#" + index)
                .withSize(spec.lengthMm(), spec.widthMm(), spec.heightMm())
                .withEmptyWeight((int) Math.round(Math.max(1, spec.emptyWeightKg())))
                .withMaxLoadWeight((int) Math.round(Math.max(1, spec.maxLoadWeightKg())))
                .build();
    }

    private List<ContainerSpecDto> orderCatalog(List<ContainerSpecDto> catalog, String preferred) {
        return catalog.stream()
                .sorted((a, b) -> {
                    if (a.type().equalsIgnoreCase(preferred)) {
                        return -1;
                    }
                    if (b.type().equalsIgnoreCase(preferred)) {
                        return 1;
                    }
                    return a.type().compareTo(b.type());
                })
                .collect(Collectors.toList());
    }

    private PackResponse mapMatches(
            String requestId,
            String strategy,
            List<Container> matches,
            List<BoxDto> boxes,
            Map<String, BoxDto> boxMap,
            String preferredType,
            List<ContainerSpecDto> catalog,
            long durationMs
    ) {
        Set<String> allIds = boxes.stream().map(BoxDto::box_id).collect(Collectors.toSet());
        Set<String> packed = new HashSet<>();
        List<PlacementDto> layout = new ArrayList<>();
        double usedVolume = 0;
        double totalWeight = 0;
        String usedType = preferredType;
        double containerVolume = 1;
        double maxLoad = 26480;
        int containersUsed = 0;

        if (matches != null) {
            int containerNo = 0;
            for (Container match : matches) {
                if (match == null || match.getStack() == null) {
                    continue;
                }
                containerNo++;
                containersUsed++;
                String desc = match.getDescription() != null ? match.getDescription() : preferredType;
                usedType = desc.contains("#") ? desc.substring(0, desc.indexOf('#')) : desc;
                containerVolume = (double) match.getLoadDx() * match.getLoadDy() * match.getLoadDz();
                if (containerVolume <= 0) {
                    containerVolume = (double) match.getDx() * match.getDy() * match.getDz();
                }
                maxLoad = match.getMaxLoadWeight();

                List<StackPlacement> placements = match.getStack().getPlacements();
                if (placements == null) {
                    continue;
                }
                int layer = 1;
                for (StackPlacement p : placements) {
                    if (p == null || p.getStackable() == null) {
                        continue;
                    }
                    String id = p.getStackable().getId();
                    packed.add(id);
                    int x = p.getAbsoluteX();
                    int y = p.getAbsoluteY();
                    int z = p.getAbsoluteZ();
                    int dx = p.getAbsoluteEndX() - x;
                    int dy = p.getAbsoluteEndY() - y;
                    int dz = p.getAbsoluteEndZ() - z;
                    usedVolume += (double) Math.max(dx, 0) * Math.max(dy, 0) * Math.max(dz, 0);
                    BoxDto src = boxMap.get(id);
                    if (src != null && src.gross_weight_kg() != null) {
                        totalWeight += src.gross_weight_kg();
                    }
                    layout.add(new PlacementDto(
                            id,
                            containerNo,
                            new PositionDto(x, y, z),
                            new SizeDto(Math.max(dx, 1), Math.max(dy, 1), Math.max(dz, 1)),
                            "LWH",
                            layer
                    ));
                }
            }
        }

        List<String> unpacked = allIds.stream()
                .filter(id -> !packed.contains(id))
                .sorted()
                .toList();

        // fallback volume from catalog
        if (containerVolume <= 1) {
            for (ContainerSpecDto s : catalog) {
                if (s.type().equalsIgnoreCase(usedType)) {
                    containerVolume = (double) s.lengthMm() * s.widthMm() * s.heightMm();
                    maxLoad = s.maxLoadWeightKg();
                    break;
                }
            }
        }

        double spaceUtil = containerVolume > 0 ? Math.min(usedVolume / containerVolume, 1.0) : 0;
        double weightUtil = maxLoad > 0 ? totalWeight / maxLoad : 0;
        boolean canFit = unpacked.isEmpty() && !layout.isEmpty();
        String message = canFit ? "可以顺利装下" : ("未完全装入: " + String.join(",", unpacked));
        String engine = "skjolber-" + strategy.toLowerCase(Locale.ROOT);

        ContainerPlanDto planDto = new ContainerPlanDto(
                usedType,
                containersUsed,
                round4(spaceUtil),
                round4(Math.min(weightUtil, 9.99)),
                canFit,
                layout,
                unpacked,
                message,
                engine
        );

        return new PackResponse(
                requestId,
                canFit,
                strategy,
                durationMs,
                containersUsed,
                unpacked,
                planDto,
                message,
                engine
        );
    }

    private static double round4(double v) {
        return Math.round(v * 10000.0) / 10000.0;
    }
}
