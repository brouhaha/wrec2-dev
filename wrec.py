#!/usr/bin/env python3

from dataclasses import dataclass
import time

import pyvisa

# XXX move into Instrument?
rm = pyvisa.ResourceManager('@py')

class Instrument:
    def __init__(self, res_id: str, name: str, reset = True):
        try:
            self.name = name
            self.visa = rm.open_resource(res_id);
            self.id = self.visa.query('*IDN?').rstrip()
            print(f'{self.name}: {self.id}')
        except:
            raise Exception(f'no {name}')
        if reset:
            self.visa.write('*rst')

    @property
    def remote(self):
        pass

    @remote.setter
    def remote(self, value = True):
        self.visa.write(('SYST:LOC', 'SYST:REM')[value])

    def poll():
        pass


class PowerSupply(Instrument):
    def __init__(self, res_id: str, name: str = 'PS', reset = True):
        super().__init__(res_id, name, reset)

    @property
    def voltage_limit(self):
        return self.visa.query_ascii_values('VOLT?', converter = 'f')[0]

    @voltage_limit.setter
    def voltage_limit(self, value):
        self.visa.write(f'VOLT {value}')

    @property
    def current_limit(self):
        return self.visa.query_ascii_values('CURR?', converter = 'f')[0]

    @current_limit.setter
    def current_limit(self, value):
        self.visa.write(f'CURR {value}')

    @property
    def output_enable(self):
        state = self.visa.query_ascii_values(f'OUTPUT:STATE?', converter = 'd')[0]
        return state == 1

    @output_enable.setter
    def output_enable(self, value: bool):
        self.visa.write(f'OUTPUT:STATE {("OFF", "ON")[value]}')
    

    @property
    def voltage_readback(self):
        return self.visa.query_ascii_values('MEAS:VOLT?', converter = 'f')[0]

    @property
    def current_readback(self):
        return self.visa.query_ascii_values('MEAS:CURR?', converter = 'f')[0]

    

        

class DMM(Instrument):
    def __init__(self, res_id: str, name: str = 'DMM', reset = True):
        super().__init__(res_id, name, reset)

    @property
    def dc_voltage(self):
        return self.visa.query_ascii_values('MEASURE:VOLTAGE:DC?', converter = 'f')[0]

    @property
    def dc_current(self, m_range = None, m_res = None):
        cmd = 'MEASURE:CURRENT:DC?'
        if m_range is not None:
            cmd += f' {m_range}'
            if m_res is not None:
                cmd += f' {m_res}'
        return self.visa.query_ascii_values('MEASURE:CURRENT:DC?', converter = 'f')[0]


@dataclass
class Capacitor:
    capacitance: float         # F
    voltage: float             # V
    max_leakage_current: float # A
    power_limit: float         # W


class WREC:
    def __init__(self, ps_res_id: str, dmm_res_id: str = None):
        self.ps = PowerSupply(ps_res_id)

        # C12 frome Varian 620/L-100 power supply  (25V + 20%)
        self.c = Capacitor(32000e-6, 30, 6e-3, 150e-3)

        # C8 frome Varian 620/L-100 power supply  (15V + 20%)
        self.c = Capacitor(23000e-6, 18, 6e-3, 150e-3)


        # Random capacitor on hand:
        # self.c = Capacitor(4700e-6, 30, 6e-3, 150e-3)

        if dmm_res_id is not None:
            self.dmm = DMM(dmm_res_id)

    def step(self):
        if self.voltage_limit >= self.c.voltage:
            return False
        self.voltage_limit += self.voltage_step
        if self.voltage_limit > self.c.voltage:
            self.voltage_limit = self.c.voltage
        self.current_limit = self.c.power_limit / self.voltage_limit
        print(f'stepping to {self.voltage_limit}V, current limit {self.current_limit}')
        self.ps.voltage_limit = self.voltage_limit
        self.ps.current_limit = self.current_limit
        return True

    def run(self):
        self.ps.remote = True
        self.ps.voltage_limit = 0
        time.sleep(0.2)
        self.ps.current_limit = 0.1
        time.sleep(0.2)
        self.ps.output_enable = True
        time.sleep(0.5)

        self.voltage_limit = 0
        self.voltage_step = 0.5
        self.step()
        while True:
            time.sleep(1)
            voltage = self.ps.voltage_readback
            current = self.ps.current_readback
            print(f'readback {voltage}V {current}A')
            if ((abs(voltage - self.voltage_limit) < 0.05) and
                (current < self.c.max_leakage_current)):
                if not self.step():
                    break

        print('shutting down')
        self.ps.output_enable = False
        time.sleep(0.5)
        self.ps.voltage_limit = 0
        self.ps.current_limit = 0
        self.ps.remote = False
        print('done')


if __name__ == '__main__':
    # get these from a config file?
    ps_res_id = "ASRL/dev/ttyUSB0"
    dmm_res_id = "USB0::0x0957::0x0607::MY47013346::INSTR"

    wrec = WREC(ps_res_id, dmm_res_id)
    wrec.run()
