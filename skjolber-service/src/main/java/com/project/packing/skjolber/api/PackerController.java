package com.project.packing.skjolber.api;

import com.project.packing.skjolber.api.dto.PackDtos.PackRequest;
import com.project.packing.skjolber.api.dto.PackDtos.PackResponse;
import com.project.packing.skjolber.service.SkjolberPackService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/packer")
@CrossOrigin(origins = "*")
public class PackerController {

    private final SkjolberPackService packService;

    public PackerController(SkjolberPackService packService) {
        this.packService = packService;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of(
                "status", "UP",
                "engine", "skjolber",
                "service", "skjolber-service"
        );
    }

    /**
     * Agent5 主接口：boxes + plan → container_plan
     */
    @PostMapping("/pack")
    public ResponseEntity<PackResponse> pack(@Valid @RequestBody PackRequest request) {
        PackResponse response = packService.pack(request);
        return ResponseEntity.ok(response);
    }
}
