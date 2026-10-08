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
    golden_id: str = 'a9bea550-bbe3-11f1-a338-51a5cc429fc7'

    def __post_init__(self):
        if self.batch_size < 1 or self.wave_size < 1:
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
        report_dir = self.report_dir or Path(f'reports/extract-validation-{self.batch_size}')
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
        if index < 2 * min(self.central_target, self.local_target):
            return 'trung_uong' if index % 2 == 0 else 'dia_phuong'
        return 'trung_uong' if self.central_target > self.local_target else 'dia_phuong'
