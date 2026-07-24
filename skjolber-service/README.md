# skjolber-service（Agent5 装载执行）

Spring Boot 3 + **skjolber/3d-bin-container-packing**，提供 3D 装柜 HTTP API。

## 要求

- JDK **17+**
- Maven 3.9+

## 启动

```bash
cd skjolber-service
mvn spring-boot:run
# 或
mvn -DskipTests package
java -jar target/skjolber-service-1.0.0.jar
```

默认端口：`8080`

## 接口

### GET `/api/v1/packer/health`

```json
{ "status": "UP", "engine": "skjolber" }
```

### POST `/api/v1/packer/pack`

请求/响应字段对齐 `docs/api-spec.md` Agent5。

Python 侧设置：

```bash
set SKJOLBER_URL=http://127.0.0.1:8080
```

## 算法

| plan.strategy 含 | Packager |
|------------------|----------|
| （默认） | `LargestAreaFitFirstPackager` |
| BRUTE | `BruteForcePackager` |
| PLAIN | `PlainPackager` |
