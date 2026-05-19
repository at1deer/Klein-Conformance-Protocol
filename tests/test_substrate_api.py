#!/usr/bin/env python3
"""
Unit tests for the Klein Substrate API.

Tests the SubstrateDriver protocol implementation using MockSubstrate.
These tests validate:
- Basic connection and capability reporting
- Frame application and sequencing
- Waveform validation
- Electrode bounds checking
- Fault injection
- E-stop and reset functionality
- Watchdog timer (Dead Man's Switch)
- Observation recording

Run with:
    python tests/test_substrate_api.py
    python -m pytest tests/test_substrate_api.py -v
"""

from __future__ import annotations

import time
import unittest

from klein.substrate.api import (
    MockSubstrate,
    OpenDropDriverStub,
    Frame,
    WaveformProfile,
    WaveformMode,
    VoltageRange,
    FrequencyRange,
    TimingProfile,
    FaultCode,
    FaultRule,
    Fault,
    SubstrateError,
    AddressingMode,
    RunOptions,
    ObservationSource,
)


class TestMockSubstrateBasics(unittest.TestCase):
    """Basic tests for MockSubstrate driver."""
    
    def setUp(self):
        """Set up a connected mock substrate for each test."""
        self.drv = MockSubstrate(max_channels=64)
        self.drv.connect("mock://test")
    
    def test_connect_sets_connected_state(self):
        """Test that connect() marks driver as connected."""
        drv = MockSubstrate()
        self.assertFalse(drv._connected)
        drv.connect("mock://new")
        self.assertTrue(drv._connected)
    
    def test_capabilities_vendor_and_model(self):
        """Test basic capability reporting."""
        caps = self.drv.get_capabilities()
        self.assertEqual(caps.device_vendor, "mock")
        self.assertEqual(caps.device_model, "MockSubstrate")
        self.assertEqual(caps.firmware, "0.0.1")
    
    def test_capabilities_channels(self):
        """Test channel count matches constructor."""
        caps = self.drv.get_capabilities()
        self.assertEqual(caps.max_channels, 64)
    
    def test_capabilities_waveforms(self):
        """Test supported waveform modes."""
        caps = self.drv.get_capabilities()
        self.assertIn(WaveformMode.DC, caps.waveforms)
        self.assertIn(WaveformMode.AC, caps.waveforms)
    
    def test_capabilities_voltage_range(self):
        """Test voltage range reporting."""
        caps = self.drv.get_capabilities()
        self.assertEqual(caps.voltage_range.v_min, 0.0)
        self.assertEqual(caps.voltage_range.v_max, 300.0)
    
    def test_topology_electrode_count(self):
        """Test electrode topology."""
        topo = self.drv.get_topology()
        self.assertEqual(len(topo.electrodes), 64)
    
    def test_topology_cartridge_id(self):
        """Test cartridge ID in topology."""
        topo = self.drv.get_topology()
        self.assertEqual(topo.cartridge_id, "MOCK-CARTRIDGE")
    
    def test_topology_adjacency(self):
        """Test electrode adjacency map."""
        topo = self.drv.get_topology()
        # Check a few adjacency relationships
        self.assertIn(1, topo.adjacency[0])  # 0 is adjacent to 1
        self.assertIn(0, topo.adjacency[1])  # 1 is adjacent to 0
        self.assertIn(2, topo.adjacency[1])  # 1 is adjacent to 2
    
    def test_not_connected_raises_error(self):
        """Test that operations before connect() raise errors."""
        drv = MockSubstrate()
        with self.assertRaises(SubstrateError):
            drv.get_capabilities()


class TestWaveformValidation(unittest.TestCase):
    """Tests for waveform parameter validation."""
    
    def setUp(self):
        self.drv = MockSubstrate(max_channels=64)
        self.drv.connect("mock://test")
    
    def test_valid_dc_waveform(self):
        """Test valid DC waveform is accepted."""
        wf = WaveformProfile(mode=WaveformMode.DC, voltage_v=100.0)
        self.drv.set_waveform(wf)  # Should not raise
    
    def test_valid_ac_waveform(self):
        """Test valid AC waveform with frequency is accepted."""
        wf = WaveformProfile(
            mode=WaveformMode.AC,
            voltage_v=200.0,
            ac_frequency_hz=1000.0
        )
        self.drv.set_waveform(wf)  # Should not raise
    
    def test_voltage_above_max_rejected(self):
        """Test voltage above maximum is rejected."""
        wf = WaveformProfile(mode=WaveformMode.DC, voltage_v=500.0)
        with self.assertRaises(SubstrateError) as ctx:
            self.drv.set_waveform(wf)
        self.assertEqual(ctx.exception.fault.code, FaultCode.UNDERVOLTAGE)
    
    def test_voltage_below_min_rejected(self):
        """Test voltage below minimum is rejected."""
        wf = WaveformProfile(mode=WaveformMode.DC, voltage_v=-10.0)
        with self.assertRaises(SubstrateError) as ctx:
            self.drv.set_waveform(wf)
        self.assertEqual(ctx.exception.fault.code, FaultCode.UNDERVOLTAGE)
    
    def test_ac_without_frequency_rejected(self):
        """Test AC mode without frequency is rejected."""
        wf = WaveformProfile(mode=WaveformMode.AC, voltage_v=200.0)
        with self.assertRaises(SubstrateError):
            self.drv.set_waveform(wf)
    
    def test_ac_frequency_out_of_range_rejected(self):
        """Test AC frequency outside range is rejected."""
        wf = WaveformProfile(
            mode=WaveformMode.AC,
            voltage_v=200.0,
            ac_frequency_hz=100000.0  # Above 50kHz max
        )
        with self.assertRaises(SubstrateError):
            self.drv.set_waveform(wf)


class TestFrameApplication(unittest.TestCase):
    """Tests for frame application."""
    
    def setUp(self):
        self.drv = MockSubstrate(max_channels=64)
        self.drv.connect("mock://test")
    
    def test_apply_simple_frame(self):
        """Test applying a simple valid frame."""
        frame = Frame(seq=1, active_electrodes=(0, 1, 2), duration_ms=20)
        ack = self.drv.apply_frame(frame)
        self.assertTrue(ack.ok)
        self.assertEqual(ack.seq, 1)
        self.assertEqual(len(ack.faults), 0)
    
    def test_frame_advances_time(self):
        """Test that frame application advances internal time."""
        frame = Frame(seq=1, active_electrodes=(0,), duration_ms=50)
        self.drv.apply_frame(frame)
        # Check internal time via observation
        obs = self.drv.read_observations()
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].time_ms, 50)
    
    def test_frame_duration_too_fast_rejected(self):
        """Test frame with duration below minimum is rejected."""
        frame = Frame(seq=1, active_electrodes=(0,), duration_ms=1)  # Below min_frame_ms=5
        ack = self.drv.apply_frame(frame)
        self.assertFalse(ack.ok)
        self.assertEqual(ack.faults[0].code, FaultCode.FRAME_TOO_FAST)
    
    def test_electrode_above_max_rejected(self):
        """Test electrode ID above max is rejected."""
        frame = Frame(seq=1, active_electrodes=(100,), duration_ms=20)  # max=64
        ack = self.drv.apply_frame(frame)
        self.assertFalse(ack.ok)
        self.assertEqual(ack.faults[0].code, FaultCode.CHANNEL_UNAVAILABLE)
    
    def test_negative_electrode_rejected(self):
        """Test negative electrode ID is rejected."""
        frame = Frame(seq=1, active_electrodes=(-1,), duration_ms=20)
        ack = self.drv.apply_frame(frame)
        self.assertFalse(ack.ok)
        self.assertEqual(ack.faults[0].code, FaultCode.CHANNEL_UNAVAILABLE)
    
    def test_empty_electrodes_accepted(self):
        """Test frame with no active electrodes is accepted."""
        frame = Frame(seq=1, active_electrodes=(), duration_ms=20)
        ack = self.drv.apply_frame(frame)
        self.assertTrue(ack.ok)


class TestSequenceExecution(unittest.TestCase):
    """Tests for sequence execution."""
    
    def setUp(self):
        self.drv = MockSubstrate(max_channels=64)
        self.drv.connect("mock://test")
    
    def test_run_simple_sequence(self):
        """Test running a simple sequence."""
        frames = [
            Frame(seq=1, active_electrodes=(0,), duration_ms=10),
            Frame(seq=2, active_electrodes=(1,), duration_ms=10),
            Frame(seq=3, active_electrodes=(2,), duration_ms=10),
        ]
        report = self.drv.run_sequence(frames)
        self.assertTrue(report.ok)
        self.assertEqual(report.last_seq, 3)
        self.assertEqual(len(report.acks), 3)
    
    def test_sequence_all_acks_successful(self):
        """Test all acks in successful sequence are ok."""
        frames = [
            Frame(seq=1, active_electrodes=(0,), duration_ms=10),
            Frame(seq=2, active_electrodes=(1,), duration_ms=10),
        ]
        report = self.drv.run_sequence(frames)
        self.assertTrue(all(a.ok for a in report.acks))
    
    def test_sequence_with_failure_partial(self):
        """Test sequence with failure (allow_partial=True)."""
        frames = [
            Frame(seq=1, active_electrodes=(0,), duration_ms=10),
            Frame(seq=2, active_electrodes=(100,), duration_ms=10),  # Invalid
            Frame(seq=3, active_electrodes=(2,), duration_ms=10),
        ]
        report = self.drv.run_sequence(frames, RunOptions(allow_partial=True))
        self.assertFalse(report.ok)
        self.assertEqual(len(report.acks), 3)  # All frames attempted
        self.assertEqual(len(report.faults), 1)
    
    def test_sequence_with_failure_strict(self):
        """Test sequence with failure (allow_partial=False)."""
        frames = [
            Frame(seq=1, active_electrodes=(0,), duration_ms=10),
            Frame(seq=2, active_electrodes=(100,), duration_ms=10),  # Invalid
            Frame(seq=3, active_electrodes=(2,), duration_ms=10),
        ]
        report = self.drv.run_sequence(frames, RunOptions(allow_partial=False))
        self.assertFalse(report.ok)
        self.assertEqual(len(report.acks), 2)  # Stopped at failure
        self.assertEqual(report.last_seq, 2)
    
    def test_empty_sequence(self):
        """Test running empty sequence."""
        report = self.drv.run_sequence([])
        self.assertTrue(report.ok)
        self.assertEqual(len(report.acks), 0)


class TestFaultInjection(unittest.TestCase):
    """Tests for deterministic fault injection."""
    
    def setUp(self):
        self.drv = MockSubstrate(max_channels=64)
        self.drv.connect("mock://test")
    
    def test_inject_fault_at_sequence(self):
        """Test fault injection at specific sequence number."""
        self.drv.add_fault_rule(FaultRule(
            when_seq=2,
            fault=Fault(FaultCode.OVERCURRENT, "Injected overcurrent"),
        ))
        
        frames = [
            Frame(seq=1, active_electrodes=(0,), duration_ms=10),
            Frame(seq=2, active_electrodes=(1,), duration_ms=10),
            Frame(seq=3, active_electrodes=(2,), duration_ms=10),
        ]
        report = self.drv.run_sequence(frames)
        
        self.assertFalse(report.ok)
        self.assertEqual(len(report.faults), 1)
        self.assertEqual(report.faults[0].code, FaultCode.OVERCURRENT)
    
    def test_inject_fault_at_electrode(self):
        """Test fault injection when specific electrode is used."""
        self.drv.add_fault_rule(FaultRule(
            when_contains_electrode=5,
            fault=Fault(FaultCode.CHANNEL_UNAVAILABLE, "Electrode 5 stuck"),
        ))
        
        # Frame without electrode 5 should succeed
        frame1 = Frame(seq=1, active_electrodes=(0, 1, 2), duration_ms=10)
        ack1 = self.drv.apply_frame(frame1)
        self.assertTrue(ack1.ok)
        
        # Frame with electrode 5 should fail
        frame2 = Frame(seq=2, active_electrodes=(4, 5, 6), duration_ms=10)
        ack2 = self.drv.apply_frame(frame2)
        self.assertFalse(ack2.ok)
        self.assertEqual(ack2.faults[0].code, FaultCode.CHANNEL_UNAVAILABLE)
    
    def test_fault_once_only_fires_once(self):
        """Test that once=True fault only fires once."""
        self.drv.add_fault_rule(FaultRule(
            when_contains_electrode=5,
            fault=Fault(FaultCode.OVERCURRENT, "One-time fault"),
            once=True,
        ))
        
        # First use of electrode 5 should trigger fault
        frame1 = Frame(seq=1, active_electrodes=(5,), duration_ms=10)
        ack1 = self.drv.apply_frame(frame1)
        self.assertFalse(ack1.ok)
        
        # Second use should succeed (fault already fired)
        frame2 = Frame(seq=2, active_electrodes=(5,), duration_ms=10)
        ack2 = self.drv.apply_frame(frame2)
        self.assertTrue(ack2.ok)


class TestEstopAndReset(unittest.TestCase):
    """Tests for emergency stop and reset."""
    
    def setUp(self):
        self.drv = MockSubstrate(max_channels=64)
        self.drv.connect("mock://test")
    
    def test_estop_sets_estopped_flag(self):
        """Test that estop() sets the estopped state."""
        self.drv.estop()
        health = self.drv.get_health()
        self.assertFalse(health.ok)
        self.assertIn("ESTOPPED", health.flags)
    
    def test_frames_rejected_after_estop(self):
        """Test that frames are rejected after estop."""
        self.drv.estop()
        frame = Frame(seq=1, active_electrodes=(0,), duration_ms=20)
        ack = self.drv.apply_frame(frame)
        self.assertFalse(ack.ok)
        self.assertEqual(ack.faults[0].code, FaultCode.EXECUTION_ABORTED)
    
    def test_reset_clears_estop(self):
        """Test that reset() clears estop state."""
        self.drv.estop()
        self.drv.reset()
        health = self.drv.get_health()
        self.assertTrue(health.ok)
        self.assertNotIn("ESTOPPED", health.flags)
    
    def test_frames_accepted_after_reset(self):
        """Test that frames are accepted after reset."""
        self.drv.estop()
        self.drv.reset()
        frame = Frame(seq=1, active_electrodes=(0,), duration_ms=20)
        ack = self.drv.apply_frame(frame)
        self.assertTrue(ack.ok)
    
    def test_reset_clears_observations(self):
        """Test that reset() clears observation history."""
        frames = [
            Frame(seq=1, active_electrodes=(0,), duration_ms=10),
            Frame(seq=2, active_electrodes=(1,), duration_ms=10),
        ]
        self.drv.run_sequence(frames)
        self.assertEqual(len(self.drv.read_observations()), 2)
        
        self.drv.reset()
        self.assertEqual(len(self.drv.read_observations()), 0)


class TestObservations(unittest.TestCase):
    """Tests for observation recording."""
    
    def setUp(self):
        self.drv = MockSubstrate(max_channels=64)
        self.drv.connect("mock://test")
    
    def test_observations_recorded_per_frame(self):
        """Test that each frame creates an observation."""
        frames = [
            Frame(seq=1, active_electrodes=(0,), duration_ms=10),
            Frame(seq=2, active_electrodes=(1,), duration_ms=10),
        ]
        self.drv.run_sequence(frames)
        
        obs = self.drv.read_observations()
        self.assertEqual(len(obs), 2)
    
    def test_observation_sequence_numbers(self):
        """Test observation sequence numbers match frames."""
        frames = [
            Frame(seq=10, active_electrodes=(0,), duration_ms=10),
            Frame(seq=20, active_electrodes=(1,), duration_ms=10),
        ]
        self.drv.run_sequence(frames)
        
        obs = self.drv.read_observations()
        self.assertEqual(obs[0].seq, 10)
        self.assertEqual(obs[1].seq, 20)
    
    def test_observation_filter_since_seq(self):
        """Test filtering observations by since_seq."""
        frames = [
            Frame(seq=1, active_electrodes=(0,), duration_ms=10),
            Frame(seq=2, active_electrodes=(1,), duration_ms=10),
            Frame(seq=3, active_electrodes=(2,), duration_ms=10),
        ]
        self.drv.run_sequence(frames)
        
        obs = self.drv.read_observations(since_seq=1)
        self.assertEqual(len(obs), 2)
        self.assertEqual(obs[0].seq, 2)
        self.assertEqual(obs[1].seq, 3)
    
    def test_observation_contains_active_electrodes(self):
        """Test observations contain active electrode data."""
        frame = Frame(seq=1, active_electrodes=(5, 10, 15), duration_ms=10)
        self.drv.apply_frame(frame)
        
        obs = self.drv.read_observations()[0]
        self.assertEqual(obs.signals["active_electrodes"], [5, 10, 15])


class TestWatchdog(unittest.TestCase):
    """Tests for watchdog timer (Dead Man's Switch)."""
    
    def test_watchdog_triggers_estop_after_timeout(self):
        """Test that exceeding max_schedule_horizon_ms triggers estop."""
        timing = TimingProfile(
            min_frame_ms=5,
            typical_jitter_ms=1,
            max_schedule_horizon_ms=50,  # 50ms watchdog
        )
        drv = MockSubstrate(timing=timing)
        drv.connect("mock://watchdog-test")
        
        # First frame OK
        frame1 = Frame(seq=1, active_electrodes=(0,), duration_ms=10)
        ack1 = drv.apply_frame(frame1)
        self.assertTrue(ack1.ok)
        
        # Wait beyond watchdog timeout
        time.sleep(0.1)  # 100ms > 50ms
        
        # Second frame should trigger watchdog estop
        frame2 = Frame(seq=2, active_electrodes=(1,), duration_ms=10)
        ack2 = drv.apply_frame(frame2)
        self.assertFalse(ack2.ok)
        self.assertEqual(ack2.faults[0].code, FaultCode.ESTOP)
    
    def test_watchdog_reset_on_connect(self):
        """Test watchdog timer resets on connect."""
        timing = TimingProfile(
            min_frame_ms=5,
            typical_jitter_ms=1,
            max_schedule_horizon_ms=50,
        )
        drv = MockSubstrate(timing=timing)
        drv.connect("mock://test1")
        
        # Apply frame to start watchdog
        frame1 = Frame(seq=1, active_electrodes=(0,), duration_ms=10)
        drv.apply_frame(frame1)
        
        # Wait beyond timeout
        time.sleep(0.1)
        
        # Reconnect should reset watchdog (though not typical usage)
        # In MockSubstrate, connect resets _last_frame_time
        drv.connect("mock://test2")
        
        # Frame should succeed (watchdog reset)
        frame2 = Frame(seq=2, active_electrodes=(1,), duration_ms=10)
        ack2 = drv.apply_frame(frame2)
        self.assertTrue(ack2.ok)


class TestOpenDropDriverStub(unittest.TestCase):
    """Tests for OpenDropDriverStub."""
    
    def setUp(self):
        self.drv = OpenDropDriverStub(channels=128)
        self.drv.connect("opendrop://stub")
    
    def test_capabilities_vendor(self):
        """Test OpenDrop-like vendor capabilities."""
        caps = self.drv.get_capabilities()
        self.assertEqual(caps.device_vendor, "GaudiLabs")
        self.assertEqual(caps.device_model, "OpenDrop-like")
    
    def test_capabilities_voltage_range(self):
        """Test OpenDrop voltage range."""
        caps = self.drv.get_capabilities()
        self.assertEqual(caps.voltage_range.v_min, 160.0)
        self.assertEqual(caps.voltage_range.v_max, 300.0)
    
    def test_voltage_below_minimum_rejected(self):
        """Test voltage below OpenDrop minimum is rejected."""
        wf = WaveformProfile(mode=WaveformMode.DC, voltage_v=100.0)
        with self.assertRaises(SubstrateError):
            self.drv.set_waveform(wf)
    
    def test_valid_opendrop_voltage_accepted(self):
        """Test valid OpenDrop voltage is accepted."""
        wf = WaveformProfile(mode=WaveformMode.DC, voltage_v=200.0)
        self.drv.set_waveform(wf)  # Should not raise
    
    def test_frame_returns_stub_detail(self):
        """Test frame acknowledgment includes stub marker."""
        frame = Frame(seq=1, active_electrodes=(0, 1), duration_ms=20)
        ack = self.drv.apply_frame(frame)
        self.assertTrue(ack.ok)
        self.assertTrue(ack.detail.get("stub", False))
    
    def test_health_includes_stub_marker(self):
        """Test health report includes stub marker."""
        health = self.drv.get_health()
        self.assertTrue(health.detail.get("stub", False))


class TestAddressingModes(unittest.TestCase):
    """Tests for addressing mode reporting."""
    
    def test_mock_substrate_direct_addressing(self):
        """Test MockSubstrate uses direct addressing."""
        drv = MockSubstrate()
        drv.connect("mock://test")
        caps = drv.get_capabilities()
        self.assertEqual(caps.addressing, AddressingMode.DIRECT)
    
    def test_opendrop_stub_direct_addressing(self):
        """Test OpenDropDriverStub uses direct addressing."""
        drv = OpenDropDriverStub()
        drv.connect("opendrop://test")
        caps = drv.get_capabilities()
        self.assertEqual(caps.addressing, AddressingMode.DIRECT)


if __name__ == "__main__":
    # Run with verbosity when executed directly
    unittest.main(verbosity=2)
