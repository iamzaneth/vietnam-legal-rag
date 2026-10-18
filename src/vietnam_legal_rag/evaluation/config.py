"""Explicit configuration shared by validation and reporting."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidationConfig:
    batch_size: int = 50
    wave_size: int = 10
    sample_manifest: Path | None = None
    report_dir: Path | None = None
    inventory: Path = Path('data/interim/discovered_urls.jsonl')
    raw_dir: Path = Path('data/raw/vbpl')
    extracted_dir: Path = Path('data/extracted/vbpl')
    central_target: int | None = None
    local_target: int | None = None
    baseline_manifests: tuple[Path, ...] = ()
    require_wave_gates: bool = False
    progress_dir: Path | None = None
    excluded_ids: tuple[str, ...] = ()
    capture_fixtures: tuple[Path, ...] = ()
    wave_offset: int = 0
    scope_prefix: tuple[str, ...] = ()
    golden_id: str = 'a9bea550-bbe3-11f1-a338-51a5cc429fc7'

    def __post_init__(self):
        if self.batch_size < 1 or self.wave_size < 1 or self.wave_offset < 0:
            raise ValueError('batch size and wave size must be positive')
        central, local = self.central_target, self.local_target
        if central is None and local is None:
            central = (self.batch_size + 1) // 2
            local = self.batch_size // 2
        elif central is None:
            central = self.batch_size - local
        elif local is None:
            local = self.batch_size - central
        if central < 0 or local < 0 or central + local != self.batch_size:
            raise ValueError('central and local targets must be nonnegative and sum to batch size')
        if (len(self.scope_prefix) > self.batch_size or
                any(s not in {'trung_uong', 'dia_phuong'} for s in self.scope_prefix) or
                self.scope_prefix.count('trung_uong') > central or
                self.scope_prefix.count('dia_phuong') > local):
            raise ValueError('scope prefix must fit the batch and actual scope targets')
        report_dir = self.report_dir or Path('reports/validation')
        object.__setattr__(self, 'central_target', central)
        object.__setattr__(self, 'local_target', local)
        object.__setattr__(self, 'report_dir', report_dir)
        object.__setattr__(self, 'sample_manifest', self.sample_manifest or report_dir / 'evidence/state.json')

    @property
    def scope_targets(self) -> dict[str, int]:
        return {'trung_uong': self.central_target, 'dia_phuong': self.local_target}

    @property
    def waves(self) -> int:
        return (self.batch_size + self.wave_size - 1) // self.wave_size

    def expected_scopes(self) -> list[str]:
        """Alternate scopes until a quota fills, then use the remaining scope."""
        return [self.scope_at(index) for index in range(self.batch_size)]

    def scope_at(self, index: int) -> str:
        if not 0 <= index < self.batch_size:
            raise IndexError('sample index is outside the configured batch')
        if index < len(self.scope_prefix):
            return self.scope_prefix[index]
        index -= len(self.scope_prefix)
        central = self.central_target - self.scope_prefix.count('trung_uong')
        local = self.local_target - self.scope_prefix.count('dia_phuong')
        if index < 2 * min(central, local):
            return 'trung_uong' if index % 2 == 0 else 'dia_phuong'
        return 'trung_uong' if central > local else 'dia_phuong'
