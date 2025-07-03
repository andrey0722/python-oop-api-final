"""Utility stuff."""


from tqdm import tqdm


class StagedTqdm(tqdm):
    """A class for more explicit progress tracking inside nested loops.

    Overrides the default tqdm progress bar format in the right section.
    It shows loop info in the form: `2/7 stages, 15/50 substages`, where
    stage - outer loop iteration, substage - inner loop iteration.

    """

    def __init__(
        self,
        *args,
        stage: int = 0,
        total_stages: int = 0,
        stage_units: str = 'stages',
        substage: int = 0,
        total_substages: int = 0,
        substage_units: str = 'substages',
        **kwargs
    ):
        """Intialize a progress bar instance.

        Args:
            stage (int): Current stage index.
            total_stages (int): Total number of stages.
            stage_units (str): The measure units to display for stage.
            substage (int): Current substage index.
            total_substages (int): Total number of substages.
            substage_units (str): The measure units to display for substage.
        """
        # Define custom properties before superclass __init__
        self.substage = substage
        self.total_substages = total_substages
        self.stage_units = stage_units
        self.stage = stage
        self.total_stages = total_stages
        self.substage_units = substage_units

        super().__init__(*args, **kwargs)

        # Override progress bar format
        # Replace the {n_fmt}/{total_fmt} part with custom format
        self.bar_format = (
            '{l_bar}{bar}| {substage_stats} '
            '[{elapsed}<{remaining}, {rate_fmt}{postfix}]'
        )

    @property
    def format_dict(self):
        """Add custom properties for the progress formatter."""
        d = super().format_dict

        # Calculate current progress position
        d['n'] = self._calc_n()
        d['total'] = self._calc_total()

        # Pre-format the substage stats
        substage_stats = []
        if self.total_stages:
            # Don't track current stage if it's absent
            substage_stats.append(
                f'{self.stage}/{self.total_stages} {self.stage_units}'
            )
        # Track current substage
        substage_stats.append(
            f'{self.substage}/{self.total_substages} {self.substage_units}'
        )
        d['substage_stats'] = ', '.join(substage_stats)

        return d

    def reset_stage(self, total_stages: int | None = None):
        """Resets stage position to 0 for repeated use.

        Args:
            total_stages (int | None): Optional value to update
                `total_stages` property. If None, then
                `total_stages` remain unchanged.
        """
        self.stage = 0
        if total_stages is not None:
            self.total_stages = total_stages
        self.initial = self._calc_n()
        self.reset(self._calc_total())

    def update_stage(self, diff_stage: int = 1):
        """Manually update the stage progress.

        Args:
            diff_stage (int): Current stage position increment.
        """
        self.stage += diff_stage
        return self.update(0)

    def reset_substage(self, total_substages: int | None = None):
        """Resets substage position to 0 for repeated use.

        Args:
            total_substages (int | None): Optional value to update
                `total_substages` property. If None, then `total_substages`
                remain unchanged.
        """
        self.substage = 0
        if total_substages is not None:
            self.total_substages = total_substages
        self.initial = self._calc_n()
        self.reset(self._calc_total())

    def update_substage(self, diff_substage: int = 1):
        """Manually update the substage progress.

        Args:
            diff_substage (int): Current substage position increment.
        """
        self.substage += diff_substage
        return self.update(0)

    def _calc_n(self):
        """Internal helper to calculate current progress position."""
        if self.total_stages:
            return self.stage * self.total_substages + self.substage
        return self.substage

    def _calc_total(self):
        """Internal helper to calculate progress total count."""
        if self.total_stages:
            return self.total_stages * self.total_substages
        return self.total_substages
