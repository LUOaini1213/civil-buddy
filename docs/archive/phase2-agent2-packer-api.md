# Agent 2（Packer）接口定义 + 推荐代码结构

> 核心：`skjolber/3d-bin-container-packing` + Spring Boot  
> 职责：根据 Plan + 箱子列表，执行 3D 装柜，返回布局 JSON。

---

## 1. REST 接口

### 1.1 执行装载（主接口）

```http
POST /api/v1/packer/pack
Content-Type: application/json
```

**Request**

```json
{
  "requestId": "req-20260724-001",
  "plan": {
    "strategy": "LARGEST_AREA_FIT_FIRST",
    "priority": "LENGTH_FIRST",
    "maxContainers": 2,
    "preferredContainerTypes": ["40HQ", "40GP"],
    "allowRotation": true,
    "constraints": {
      "noStackBoxIds": ["BOX-03"],
      "fixedBottomBoxIds": ["BOX-01"],
      "separateGroups": []
    },
    "timeoutMs": 5000,
    "hints": []
  },
  "boxes": [
    {
      "boxId": "BOX-01",
      "boxType": "6米铁架",
      "lengthMm": 6000,
      "widthMm": 1100,
      "heightMm": 1550,
      "weightKg": 251.0,
      "grossWeightKg": 1161.0,
      "special": ["超长"],
      "allowRotate": false,
      "stackable": false
    }
  ],
  "containerCatalog": [
    {
      "type": "40HQ",
      "lengthMm": 12032,
      "widthMm": 2352,
      "heightMm": 2698,
      "emptyWeightKg": 3900,
      "maxLoadWeightKg": 26480
    }
  ]
}
```

**Response 200**

```json
{
  "requestId": "req-20260724-001",
  "success": true,
  "algorithm": "LARGEST_AREA_FIT_FIRST",
  "durationMs": 42,
  "containersUsed": 1,
  "unpackedBoxIds": [],
  "layouts": [
    {
      "containerIndex": 0,
      "containerType": "40HQ",
      "containerId": "CTR-01",
      "placements": [
        {
          "boxId": "BOX-01",
          "xMm": 0,
          "yMm": 0,
          "zMm": 0,
          "dxMm": 6000,
          "dyMm": 1100,
          "dzMm": 1550,
          "rotated": false,
          "level": 0
        }
      ],
      "metrics": {
        "volumeUtilPct": 18.5,
        "weightUtilPct": 4.4,
        "usedVolumeMm3": 10230000000,
        "containerVolumeMm3": 76200000000,
        "totalLoadWeightKg": 1161.0,
        "maxLoadWeightKg": 26480
      }
    }
  ],
  "message": "OK"
}
```

**Response 业务失败（仍 200，由 success=false 表达）**

```json
{
  "requestId": "req-20260724-001",
  "success": false,
  "unpackedBoxIds": ["BOX-02", "BOX-04"],
  "layouts": [],
  "message": "无法在 maxContainers=1 内装完"
}
```

### 1.2 健康检查

```http
GET /api/v1/packer/health
→ { "status": "UP", "skjolber": "4.2.x" }
```

### 1.3 编排总入口（可选，放 orchestration）

```http
POST /api/v1/orchestration/run
```

Body：`{ "boxes": [...], "options": { "maxIteration": 3, "preferredContainerTypes": ["40HQ"] } }`  
内部：Planner → Packer → Evaluator 循环。

---

## 2. 内部 Java API（包内契约）

```java
public interface PackerAgent {
    PackResult pack(PackCommand command);
}

public record PackCommand(
    String requestId,
    LoadPlan plan,
    List<CargoBox> boxes,
    List<ContainerSpec> containerCatalog
) {}

public record LoadPlan(
    PackStrategy strategy,          // LAFF | BRUTE_FORCE | PLAIN | FAST_LAFF
    PriorityRule priority,          // LENGTH_FIRST | WEIGHT_FIRST | VOLUME_FIRST
    int maxContainers,
    List<String> preferredContainerTypes,
    boolean allowRotation,
    PlanConstraints constraints,
    long timeoutMs,
    List<String> hints
) {}

public record CargoBox(
    String boxId,
    String boxType,
    int lengthMm,
    int widthMm,
    int heightMm,
    double weightKg,                // 建议用毛重参与限重
    List<String> special,
    boolean allowRotate,
    boolean stackable
) {}

public record PackResult(
    boolean success,
    String algorithm,
    long durationMs,
    List<ContainerLayout> layouts,
    List<String> unpackedBoxIds,
    String message
) {}

public record ContainerLayout(
    int containerIndex,
    String containerType,
    String containerId,
    List<Placement> placements,
    LayoutMetrics metrics
) {}

public record Placement(
    String boxId,
    int xMm, int yMm, int zMm,
    int dxMm, int dyMm, int dzMm,
    boolean rotated,
    int level
) {}
```

---

## 3. 推荐代码结构

```
packer/
├── PackerAgent.java                 # 接口
├── PackerAgentImpl.java             # 编排：排序 → 选算法 → 调 skjolber → 映射结果
├── api/
│   ├── PackerController.java        # REST
│   ├── dto/
│   │   ├── PackRequest.java
│   │   ├── PackResponse.java
│   │   └── ...
│   └── PackerExceptionHandler.java
├── domain/
│   ├── CargoBox.java
│   ├── LoadPlan.java
│   ├── PackResult.java
│   ├── ContainerSpec.java
│   └── enums/
│       ├── PackStrategy.java
│       └── PriorityRule.java
├── skjolber/
│   ├── SkjolberPackagerFactory.java # 创建 LAFF / BruteForce / Plain
│   ├── SkjolberMapper.java          # CargoBox ↔ BoxItem, ContainerSpec ↔ Container
│   ├── SkjolberPackService.java     # 真正调用 packager.newResultBuilder()...
│   └── WeightScaler.java            # kg → 整数重量（×1000 用 g，或四舍五入 kg）
├── sort/
│   └── BoxPrioritySorter.java       # 按 Plan.priority 预排序（配合算法）
└── config/
    ├── PackerProperties.java        # timeout、默认柜型
    └── PackerConfiguration.java
```

---

## 4. skjolber 封装要点（实现伪代码）

```java
@Service
public class SkjolberPackService {

  public PackResult pack(LoadPlan plan, List<CargoBox> boxes, List<ContainerSpec> catalog) {
    Packager packager = packagerFactory.create(plan.strategy());

    List<BoxItem> products = boxes.stream()
        .map(b -> {
          var builder = Box.newBuilder()
              .withId(b.boxId())
              .withSize(b.lengthMm(), b.widthMm(), b.heightMm())
              .withWeight(weightScaler.toInt(b.weightKg()));
          if (b.allowRotate() && plan.allowRotation()) {
            builder.withRotate3D();
          }
          // 超长件：可只允许绕竖直轴旋转 → 用 withRotate2D / 自定义 control（视版本 API）
          return new BoxItem(builder.build(), 1);
        })
        .toList();

    List<ContainerItem> containerItems = ContainerItem.newListBuilder()
        .withContainer(
            // 按 preferredContainerTypes 顺序注册多种柜型
            // 每种可 withContainer(container, maxCount)
        )
        .build();

    long deadline = System.currentTimeMillis() + plan.timeoutMs();

    PackagerResult result = packager.newResultBuilder()
        .withContainerItems(containerItems)
        .withBoxItems(products)
        .withMaxContainerCount(plan.maxContainers())
        // 若 API 支持 deadline，brute-force 务必设置
        .build();

    return mapper.toPackResult(result, plan, boxes, catalog);
  }
}
```

**Factory 推荐**

```java
public Packager create(PackStrategy s) {
  return switch (s) {
    case LARGEST_AREA_FIT_FIRST -> LargestAreaFitFirstPackager.newBuilder().build();
    case FAST_LAFF -> FastLargestAreaFitFirstPackager.newBuilder().build();
    case BRUTE_FORCE -> BruteForcePackager.newBuilder().build();
    case PLAIN -> PlainPackager.newBuilder().build();
  };
}
```

**注意**

1. Packager 实例 **线程安全**，可做成单例 Bean。  
2. 单位自洽即可：全流程 **mm + kg**。  
3. 重量：skjolber 常用 `int` weight → 建议 **千克四舍五入** 或 **克（×1000）**，全项目统一。  
4. 超长件（如 6m 铁架）建议 `allowRotate=false` 或仅允许水平面旋转，避免「竖起来装」的 equest。  
5. 一阶段 `结构不通过` 的箱子：Packer 可拒绝入算，或原样尝试但 Evaluator 一票否决。

---

## 5. 从一阶段 JSON 适配（Python → Java）

一阶段 `boxes` 示例字段 → Request.boxes：

```text
箱号              → boxId
箱型              → boxType
外尺寸_mm.长/宽/高 → lengthMm/widthMm/heightMm
毛重_kg           → weightKg
特殊属性          → special；含「超长」→ allowRotate=false, stackable=false
结构结论=不通过   → 可选：orchestration 拦截，不进 Packer
```

Python 侧调用示例：

```python
import requests
resp = requests.post(
    "http://localhost:8080/api/v1/packer/pack",
    json={"requestId": run_id, "plan": plan, "boxes": boxes_dto, "containerCatalog": catalog},
    timeout=30,
)
```

LangGraph 二阶段节点可把现有 `consolidation_agent` 换成 **HTTP 调 Packer**，本地 1D 算法作 fallback。

---

## 6. 验收标准（Agent 2 单独可测）

| 用例 | 期望 |
|------|------|
| 1 个小箱进 40HQ | success=true，1 柜，placement 原点附近 |
| 3 个 6m 铁架 + maxContainers=1 + 20GP | success=false 或 unpacked 非空 |
| 多箱 40HQ | volumeUtilPct 合理，无坐标越界 |
| allowRotate=false 的超长件 | dx/dy/dz 与输入一致（未竖放） |
| timeoutMs 很短 + BRUTE_FORCE | 不挂死，返回失败或部分结果 |

单元测试：不启 Spring，直接测 `SkjolberPackService`。  
集成测试：`@SpringBootTest` + MockMvc 打 `/api/v1/packer/pack`。

---

## 7. pom 片段

```xml
<properties>
  <java.version>17</java.version>
  <3d-bin-container-packing.version>4.2.1</3d-bin-container-packing.version>
</properties>

<dependencies>
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
  </dependency>
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-validation</artifactId>
  </dependency>
  <dependency>
    <groupId>com.github.skjolber.3d-bin-container-packing</groupId>
    <artifactId>core</artifactId>
    <version>${3d-bin-container-packing.version}</version>
  </dependency>
</dependencies>
```

---

## 8. 与 Agent 1 / 3 的边界（避免职责糊）

| 不做（留给别人） | Packer 只做 |
|------------------|------------|
| 决定几个柜、什么策略 | 执行 Plan，不擅自改策略 |
| 写自然语言报告 | 返回结构化 Layout + metrics |
| 结构强度验算（一阶段已做） | 3D 几何装载与柜限重 |

Planner 输出 Plan；Packer 只消费 Plan；Evaluator 只读 Layout 打分。
