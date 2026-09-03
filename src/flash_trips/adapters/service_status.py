from flash_trips.kernel.service_status import ServiceStatus


class StaticServiceStatus:
    def read(self) -> ServiceStatus:
        return ServiceStatus()
