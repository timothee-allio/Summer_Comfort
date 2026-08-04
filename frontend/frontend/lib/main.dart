import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:web/web.dart' as web;
import 'dart:js_interop';

void main() {
  runApp(const SummerComfortApp());
}

class SummerComfortApp extends StatelessWidget {
  const SummerComfortApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Paris Thermal Simulation',
      theme: ThemeData(
        primarySwatch: Colors.blueGrey,
        scaffoldBackgroundColor: Colors.grey[100],
      ),
      home: const DashboardScreen(),
    );
  }
}

class SimRecord {
  final int runId;
  final String scenario;
  final double wallR;
  final double globalWindowArea;
  final double overhang;
  final double ventilation;
  final bool shadingEnabled;
  final double totalCooling;
  final double totalHeating;

  SimRecord({
    required this.runId,
    required this.scenario,
    required this.wallR,
    required this.globalWindowArea,
    required this.overhang,
    required this.ventilation,
    required this.shadingEnabled,
    required this.totalCooling,
    required this.totalHeating,
  });
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  // Building Parameters
  double wallRValue = 4.0;
  double globalWindowArea = 15.0;
  double overhangDepth = 0.8;
  double maxVentilation = 12.0;
  bool externalShadingEnabled = false;
  String selectedScenario = "2090_heatwave";

  // Heatmap State
  String mapXAxis = 'globalWindowArea';
  String mapYAxis = 'overhang';
  String mapZMetric = 'cooling';

  // History & Tracking
  List<SimRecord> runHistory = [];
  int runCounter = 1;

  // Simulation Results
  bool isLoading = false;
  Map<String, dynamic>? simResults;

  Future<void> runSimulation() async {
    setState(() => isLoading = true);

    try {
      final response = await http.post(
        Uri.parse('http://127.0.0.1:8000/api/simulate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          "wall_r": wallRValue,
          "global_window_area": globalWindowArea,
          "overhang_depth": overhangDepth,
          "vent_max_ach": maxVentilation,
          "external_shading_enabled":
              externalShadingEnabled, // <-- Fix this key!
          "weather_case": selectedScenario,
        }),
      );

      if (response.statusCode == 200) {
        setState(() {
          simResults = jsonDecode(response.body);

          runHistory.insert(
            0,
            SimRecord(
              runId: runCounter++,
              scenario: selectedScenario,
              wallR: wallRValue,
              globalWindowArea: globalWindowArea,
              overhang: overhangDepth,
              ventilation: maxVentilation,
              shadingEnabled: externalShadingEnabled,
              totalCooling: simResults!['summary']['total_cooling_kwh'] ?? 0.0,
              totalHeating: simResults!['summary']['total_heating_kwh'] ?? 0.0,
            ),
          );
        });
      } else {
        debugPrint("Server Error: ${response.statusCode}");
      }
    } catch (e) {
      debugPrint("Connection Error: $e");
    } finally {
      setState(() => isLoading = false);
    }
  }

  void _downloadCSV() {
    if (simResults == null) return;

    final tOut = simResults!['t_out'] as List;
    final tAir = simResults!['t_air'] as List;
    final tOp = simResults!['t_op'] as List;
    final qCool = simResults!['q_cool'] as List;
    final achVent = simResults!['ach_vent'] as List;

    StringBuffer csvData = StringBuffer();

    csvData.write('\uFEFF');
    csvData.writeln(
      "Hour,T_out (°C),T_air (°C),T_op (°C),Cooling (W),Ventilation (ACH)",
    );

    for (int i = 0; i < tOut.length; i++) {
      csvData.writeln(
        "${i + 1},"
        "${tOut[i].toStringAsFixed(2)},"
        "${tAir[i].toStringAsFixed(2)},"
        "${tOp[i].toStringAsFixed(2)},"
        "${qCool[i].toStringAsFixed(1)},"
        "${achVent[i].toStringAsFixed(2)}",
      );
    }

    final bytes = utf8.encode(csvData.toString());

    final blob = web.Blob(
      [bytes.toJS].toJS,
      web.BlobPropertyBag(type: 'text/csv;charset=utf-8'),
    );

    final url = web.URL.createObjectURL(blob);

    final anchor = web.HTMLAnchorElement()
      ..href = url
      ..download = "paris_${selectedScenario}_simulation.csv";

    web.document.body?.append(anchor);
    anchor.click();
    anchor.remove();
    web.URL.revokeObjectURL(url);
  }

  void _downloadLedgerCSV() {
    if (runHistory.isEmpty) return;

    StringBuffer csvData = StringBuffer();

    csvData.write('\uFEFF');
    csvData.writeln(
      "Run ID,Scenario,Wall R-Value (m²K/W),Global Window Area (m²),Overhang Depth (m),Ventilation (ACH),Shading Enabled,Total Cooling (kWh),Total Heating (kWh)",
    );

    for (var r in runHistory) {
      csvData.writeln(
        "${r.runId},"
        "${r.scenario},"
        "${r.wallR.toStringAsFixed(2)},"
        "${r.globalWindowArea.toStringAsFixed(2)},"
        "${r.overhang.toStringAsFixed(2)},"
        "${r.ventilation.toStringAsFixed(2)},"
        "${r.shadingEnabled ? 'On' : 'Off'},"
        "${r.totalCooling.toStringAsFixed(2)},"
        "${r.totalHeating.toStringAsFixed(2)}",
      );
    }

    final bytes = utf8.encode(csvData.toString());

    final blob = web.Blob(
      [bytes.toJS].toJS,
      web.BlobPropertyBag(type: 'text/csv;charset=utf-8'),
    );

    final url = web.URL.createObjectURL(blob);

    final anchor = web.HTMLAnchorElement()
      ..href = url
      ..download = "simulation_run_ledger.csv";

    web.document.body?.append(anchor);
    anchor.click();
    anchor.remove();
    web.URL.revokeObjectURL(url);
  }

  @override
  void initState() {
    super.initState();
    runSimulation();
  }

  double _getParamMin(String param) => param == 'wallR' ? 0.5 : 0.0;

  double _getParamMax(String param) {
    switch (param) {
      case 'wallR':
        return 10.0;
      case 'globalWindowArea':
        return 60.0;
      case 'overhang':
        return 2.0;
      case 'ventilation':
        return 20.0;
      default:
        return 10.0;
    }
  }

  double _getCurrentParamValue(String param) {
    switch (param) {
      case 'wallR':
        return wallRValue;
      case 'globalWindowArea':
        return globalWindowArea;
      case 'overhang':
        return overhangDepth;
      case 'ventilation':
        return maxVentilation;
      default:
        return 0.0;
    }
  }

  Widget _buildRunLedger() {
    if (runHistory.isEmpty) return const SizedBox.shrink();

    return Container(
      height: 120,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            color: Colors.grey.shade200,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Simulation Run Ledger',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                TextButton.icon(
                  onPressed: _downloadLedgerCSV,
                  icon: const Icon(Icons.download, size: 16),
                  label: const Text(
                    'Download all runs (.csv)',
                    style: TextStyle(fontSize: 12),
                  ),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 0,
                    ),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: runHistory.length,
              itemBuilder: (context, index) {
                final r = runHistory[index];
                return Container(
                  decoration: BoxDecoration(
                    border: Border(
                      bottom: BorderSide(color: Colors.grey.shade100),
                    ),
                  ),
                  child: ListTile(
                    dense: true,
                    leading: CircleAvatar(
                      backgroundColor: Colors.blueGrey,
                      radius: 14,
                      child: Text(
                        '${r.runId}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                        ),
                      ),
                    ),
                    title: Text(
                      '${r.scenario.replaceAll('_', ' ').toUpperCase()} | Cool: ${r.totalCooling.toStringAsFixed(0)} kWh | Heat: ${r.totalHeating.toStringAsFixed(0)} kWh',
                    ),
                    subtitle: Text(
                      'R: ${r.wallR.toStringAsFixed(2)} | Win: ${r.globalWindowArea.toStringAsFixed(1)}m² | Overhang: ${r.overhang.toStringAsFixed(1)}m | Vent: ${r.ventilation.toStringAsFixed(1)}ACH | Shades: ${r.shadingEnabled ? 'ON' : 'OFF'}',
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Paris Thermal Simulation'),
        elevation: 0,
      ),
      body: Row(
        children: [
          // LEFT PANEL: Controls
          // LEFT PANEL: Controls
          Expanded(
            flex: 1,
            child: Material(
              color: Colors.white,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Building Parameters',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),

                    // DYNAMIC HOUSE CONTEXT BOX
                    Container(
                      padding: const EdgeInsets.all(12),
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.blueGrey.shade50,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.blueGrey.shade200),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Fixed Scientific Assumptions',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Colors.blueGrey,
                            ),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            '• The house is 8.0 m wide, 12.5 m long, and 2.7 m high:\n'
                            '  - Floor Area: 100 m²\n'
                            '  - Volume: 250 m³\n'
                            '• Facade Areas:\n'
                            '  - North/South: 21,6 m²\n'
                            '  - East/West: 33,75 m²\n'
                            '• Overhang: South facade only\n'
                            '• HVAC: Ideal heating (6.0 kW, 20°C) & cooling (5.0 kW, 26°C)',
                            style: TextStyle(
                              fontSize: 13,
                              height: 1.5,
                              color: Colors.blueGrey,
                            ),
                          ),
                          const Divider(color: Colors.blueGrey, height: 16),
                          const Text(
                            'Dynamic Glazing Distribution:',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 13,
                              color: Colors.blueGrey,
                            ),
                          ),
                          const SizedBox(height: 4),
                          // This text dynamically updates based on the slider state
                          Text(
                            'Total Window Area: ${globalWindowArea.toStringAsFixed(1)} m²\n'
                            '→ South Facade: ${(globalWindowArea / 4).toStringAsFixed(2)} m²\n'
                            '→ North Facade: ${(globalWindowArea / 4).toStringAsFixed(2)} m²\n'
                            '→ East Facade: ${(globalWindowArea / 4).toStringAsFixed(2)} m²\n'
                            '→ West Facade: ${(globalWindowArea / 4).toStringAsFixed(2)} m²',
                            style: const TextStyle(
                              fontSize: 13,
                              height: 1.5,
                              color: Colors.blueGrey,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Divider(),
                    _buildSlider(
                      'Wall Insulation R-Value (m²K/W)',
                      wallRValue,
                      0.5,
                      10.0,
                      (val) => setState(() => wallRValue = val),
                    ),
                    _buildSlider(
                      'Global Window Area (m²)',
                      globalWindowArea,
                      2.0,
                      60.0,
                      (val) => setState(() => globalWindowArea = val),
                    ),
                    _buildSlider(
                      'South Overhang Depth (m)',
                      overhangDepth,
                      0.0,
                      2.0,
                      (val) => setState(() => overhangDepth = val),
                    ),
                    _buildSlider(
                      'Night Ventilation (ACH)',
                      maxVentilation,
                      0.0,
                      20.0,
                      (val) => setState(() => maxVentilation = val),
                    ),
                    const SizedBox(height: 8),
                    SwitchListTile.adaptive(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('East & West External Solar Shading'),
                      subtitle: const Text(
                        'Deploys above 24 °C indoor air; blocks 80% of window solar gains',
                      ),
                      value: externalShadingEnabled,
                      onChanged: (value) =>
                          setState(() => externalShadingEnabled = value),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Climate Scenario',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    DropdownButtonFormField<String>(
                      initialValue: selectedScenario,
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: '2090_heatwave',
                          child: Text('Year 2090 with Extreme Heatwave'),
                        ),
                        DropdownMenuItem(
                          value: '2090_typical',
                          child: Text('Year 2090 with Typical Summer'),
                        ),
                        DropdownMenuItem(
                          value: '2050_heatwave',
                          child: Text('Year 2050 with Extreme Heatwave'),
                        ),
                        DropdownMenuItem(
                          value: '2050_typical',
                          child: Text('Year 2050 with Typical Summer'),
                        ),
                      ],
                      onChanged: (val) {
                        if (val != null) setState(() => selectedScenario = val);
                      },
                    ),
                    const SizedBox(height: 32),
                    SizedBox(
                      width: double.infinity,
                      height: 50,
                      child: ElevatedButton(
                        onPressed: isLoading ? null : runSimulation,
                        child: isLoading
                            ? const CircularProgressIndicator(
                                color: Colors.white,
                              )
                            : const Text(
                                'Run Simulation',
                                style: TextStyle(fontSize: 16),
                              ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // RIGHT PANEL: Results
          Expanded(
            flex: 2,
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 1. VISUAL DIAGRAM
                  Center(
                    child: HouseDiagram(
                      shadingEnabled: externalShadingEnabled,
                      overhangDepth: overhangDepth,
                      globalWindowArea: globalWindowArea,
                      wallRValue: wallRValue,
                    ),
                  ),
                  const SizedBox(height: 32),

                  // 2. SIMULATION RESULTS HEADER
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Simulation Results',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (simResults != null)
                        OutlinedButton.icon(
                          onPressed: _downloadCSV,
                          icon: const Icon(Icons.download, size: 18),
                          label: const Text(
                            'Download Hourly Results Current Simulation (.csv)',
                          ),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.blueGrey,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // 3. STAT CARDS
                  if (simResults != null)
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        _buildStatCard(
                          'Total Cooling',
                          '${simResults!['summary']['total_cooling_kwh']?.toStringAsFixed(0) ?? 0} kWh',
                          Colors.blue,
                        ),
                        _buildStatCard(
                          'Total Heating',
                          '${simResults!['summary']['total_heating_kwh']?.toStringAsFixed(0) ?? 0} kWh',
                          Colors.orange,
                        ),
                        _buildStatCard(
                          'Hours > 26°C',
                          '${simResults!['summary']['hours_above_26'] ?? 0} hrs',
                          const Color.fromARGB(255, 255, 196, 1),
                        ),
                        _buildStatCard(
                          'Hours > 28°C',
                          '${simResults!['summary']['hours_above_28'] ?? 0} hrs',
                          Colors.red,
                        ),
                      ],
                    ),

                  const SizedBox(height: 24),

                  // 4. RUN LEDGER
                  _buildRunLedger(),
                  const SizedBox(height: 24),

                  // 5. CONTOUR HEATMAP DASHBOARD
                  Container(
                    height: 520,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey.shade300),
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Optimal Combinations Map',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Row(
                              children: [
                                const Text('Metric (Color Scale) : '),
                                DropdownButton<String>(
                                  value: mapZMetric,
                                  items: const [
                                    DropdownMenuItem(
                                      value: 'cooling',
                                      child: Text('Cooling Demand'),
                                    ),
                                    DropdownMenuItem(
                                      value: 'heating',
                                      child: Text('Heating Demand'),
                                    ),
                                  ],
                                  onChanged: (val) =>
                                      setState(() => mapZMetric = val!),
                                ),
                              ],
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            const Text(
                              'Parameter on Y-Axis: ',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey,
                              ),
                            ),
                            DropdownButton<String>(
                              value: mapYAxis,
                              style: const TextStyle(
                                fontSize: 12,
                                color: Colors.blueGrey,
                              ),
                              items: const [
                                DropdownMenuItem(
                                  value: 'wallR',
                                  child: Text('Wall R-Value'),
                                ),
                                DropdownMenuItem(
                                  value: 'globalWindowArea',
                                  child: Text('Global Window Area'),
                                ),
                                DropdownMenuItem(
                                  value: 'overhang',
                                  child: Text('Overhang Depth'),
                                ),
                                DropdownMenuItem(
                                  value: 'ventilation',
                                  child: Text('Ventilation'),
                                ),
                              ],
                              onChanged: (val) =>
                                  setState(() => mapYAxis = val!),
                            ),
                            const SizedBox(width: 24),
                            const Text(
                              'Parameter on X-Axis: ',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey,
                              ),
                            ),
                            DropdownButton<String>(
                              value: mapXAxis,
                              style: const TextStyle(
                                fontSize: 12,
                                color: Colors.blueGrey,
                              ),
                              items: const [
                                DropdownMenuItem(
                                  value: 'wallR',
                                  child: Text('Wall R-Value'),
                                ),
                                DropdownMenuItem(
                                  value: 'globalWindowArea',
                                  child: Text('Global Window Area'),
                                ),
                                DropdownMenuItem(
                                  value: 'overhang',
                                  child: Text('Overhang Depth'),
                                ),
                                DropdownMenuItem(
                                  value: 'ventilation',
                                  child: Text('Ventilation'),
                                ),
                              ],
                              onChanged: (val) =>
                                  setState(() => mapXAxis = val!),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Expanded(
                          child: ContourHeatmap(
                            xAxisLabel: mapXAxis,
                            yAxisLabel: mapYAxis,
                            activeMetric: mapZMetric,
                            baseWallR: wallRValue,
                            baseGlobalWindowArea: globalWindowArea,
                            baseOverhang: overhangDepth,
                            baseVentilation: maxVentilation,
                            shadingEnabled: externalShadingEnabled,
                            scenario: selectedScenario,
                            currentX: _getCurrentParamValue(mapXAxis),
                            currentY: _getCurrentParamValue(mapYAxis),
                            minX: _getParamMin(mapXAxis),
                            maxX: _getParamMax(mapXAxis),
                            minY: _getParamMin(mapYAxis),
                            maxY: _getParamMax(mapYAxis),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSlider(
    String label,
    double value,
    double min,
    double max,
    Function(double) onChanged,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$label: ${value.toStringAsFixed(2)}'),
          Slider(
            value: value,
            min: min,
            max: max,
            divisions: 100,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String title, String value, Color color) {
    return Expanded(
      child: Card(
        elevation: 2,
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            children: [
              Text(
                title,
                style: const TextStyle(fontSize: 14, color: Colors.grey),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                value,
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------
// DIAGRAM PAINTER
// ---------------------------------------------------------
class HouseDiagram extends StatelessWidget {
  const HouseDiagram({
    super.key,
    required this.shadingEnabled,
    required this.overhangDepth,
    required this.globalWindowArea,
    required this.wallRValue,
  });

  final bool shadingEnabled;
  final double overhangDepth;
  final double globalWindowArea;
  final double wallRValue;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: SizedBox(
        width: double.infinity,
        height: 300,
        child: CustomPaint(
          painter: _HouseDiagramPainter(
            shadingEnabled,
            overhangDepth,
            globalWindowArea,
            wallRValue,
          ),
        ),
      ),
    );
  }
}

class _HouseDiagramPainter extends CustomPainter {
  _HouseDiagramPainter(
    this.shadingEnabled,
    this.overhangDepth,
    this.globalWindowArea,
    this.wallRValue,
  );

  final bool shadingEnabled;
  final double overhangDepth;
  final double globalWindowArea;
  final double wallRValue;

  static const _outline = Color(0xFF263238);
  static const _shade = Color(0xFF8B1E3F);

  @override
  void paint(Canvas canvas, Size size) {
    // SCALING MULTIPLIER
    const double m = 1.6;

    final double cx = size.width / 2;
    // FIXED: Pushed the center point further down (from 40*m to 60*m) to fit the roof
    final double cy = size.height / 2 + (60 * m);

    final Offset axisX = const Offset(-0.866, -0.5);
    final Offset axisY = const Offset(0.866, -0.5);
    final Offset axisZ = const Offset(0, -1.0);

    Offset to2D(double x, double y, double z) {
      return Offset(
        cx + x * axisX.dx + y * axisY.dx + z * axisZ.dx,
        cy + x * axisX.dy + y * axisY.dy + z * axisZ.dy,
      );
    }

    void drawPoly(List<Offset> points, Paint fill, Paint stroke) {
      final path = Path()..moveTo(points[0].dx, points[0].dy);
      for (int i = 1; i < points.length; i++) {
        path.lineTo(points[i].dx, points[i].dy);
      }
      path.close();
      canvas.drawPath(path, fill);
      canvas.drawPath(path, stroke);
    }

    final double hLen = 80 * m;
    final double hWid = 125 * m;
    final double hHt = 40 * m;

    final double strokeWidth = 1.0 + (wallRValue * 0.7);
    final wallStroke = Paint()
      ..color = Colors.grey.shade800
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = strokeWidth;

    final roofFill = Paint()
      ..color = Colors.grey.shade300
      ..style = PaintingStyle.fill;
    final eastFill = Paint()
      ..color = Colors.grey.shade400
      ..style = PaintingStyle.fill;
    final southFill = Paint()
      ..color = Colors.grey.shade100
      ..style = PaintingStyle.fill;

    // Draw Walls
    drawPoly(
      [to2D(0, 0, 0), to2D(0, hWid, 0), to2D(0, hWid, hHt), to2D(0, 0, hHt)],
      eastFill,
      wallStroke,
    );
    drawPoly(
      [to2D(0, 0, 0), to2D(hLen, 0, 0), to2D(hLen, 0, hHt), to2D(0, 0, hHt)],
      southFill,
      wallStroke,
    );
    drawPoly(
      [
        to2D(0, 0, hHt),
        to2D(hLen, 0, hHt),
        to2D(hLen, hWid, hHt),
        to2D(0, hWid, hHt),
      ],
      roofFill,
      wallStroke,
    );

    final double facadeWinArea = globalWindowArea / 4.0;
    final double wHeight = 20 * m;

    final double wWidth =
        ((10 + (facadeWinArea * 4.0)).clamp(5.0, 80 - 10)) * m;
    final double eWidth =
        ((10 + (facadeWinArea * 4.0)).clamp(5.0, 125 - 10)) * m;

    final double wStartX = (hLen - wWidth) / 2;
    final double wEndX = wStartX + wWidth;
    final double eStartY = (hWid - eWidth) / 2;
    final double eEndY = eStartY + eWidth;

    final double wStartZ = 12 * m;
    final double wEndZ = wStartZ + wHeight;

    final windowFill = Paint()
      ..color = Colors.lightBlueAccent.withValues(alpha: 0.5)
      ..style = PaintingStyle.fill;
    final windowStroke = Paint()
      ..color = Colors.blue.shade700
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;

    // South Window
    drawPoly(
      [
        to2D(wStartX, 0, wStartZ),
        to2D(wEndX, 0, wStartZ),
        to2D(wEndX, 0, wEndZ),
        to2D(wStartX, 0, wEndZ),
      ],
      windowFill,
      windowStroke,
    );

    // East Window
    drawPoly(
      [
        to2D(0, eStartY, wStartZ),
        to2D(0, eEndY, wStartZ),
        to2D(0, eEndY, wEndZ),
        to2D(0, eStartY, wEndZ),
      ],
      windowFill,
      windowStroke,
    );

    // Overhang
    if (overhangDepth > 0) {
      final double oDepth = overhangDepth * 15 * m;
      final double oDrop = overhangDepth * 8 * m;
      final overhangFill = Paint()
        ..color = Colors.brown.shade400
        ..style = PaintingStyle.fill;
      final overhangStroke = Paint()
        ..color = Colors.brown.shade900
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round
        ..strokeWidth = 2;

      drawPoly(
        [
          to2D(wStartX - (3 * m), 0, wEndZ + (3 * m)),
          to2D(wEndX + (3 * m), 0, wEndZ + (3 * m)),
          to2D(wEndX + (3 * m), -oDepth, wEndZ + (3 * m) - oDrop),
          to2D(wStartX - (3 * m), -oDepth, wEndZ + (3 * m) - oDrop),
        ],
        overhangFill,
        overhangStroke,
      );
    }

    // Shades
    if (shadingEnabled) {
      final blind = Paint()
        ..color = _shade
        ..strokeWidth = 4 * (m * 0.8)
        ..strokeCap = StrokeCap.round;

      for (double z = wStartZ + (2 * m); z <= wEndZ; z += (5 * m)) {
        canvas.drawLine(
          to2D(-(3 * m), eStartY - (2 * m), z),
          to2D(-(3 * m), eEndY + (2 * m), z),
          blind,
        );
      }
    }

    // TOP LEFT: Shade Status
    _label(
      canvas,
      shadingEnabled ? 'EXTERNAL SHADES ON' : 'EXTERNAL SHADES OFF',
      const Offset(20, 20),
      color: shadingEnabled ? _shade : Colors.grey.shade500,
    );

    // BOTTOM: Anchored directly below the specific walls
    final Offset southBaseCenter = to2D(hLen / 2, 0, 0);
    final Offset eastBaseCenter = to2D(0, hWid / 2, 0);

    // FIXED: Adjusted offsets to push texts further away from the drawing
    _label(canvas, 'South facade', southBaseCenter + const Offset(-60, 25));
    _label(canvas, 'East facade', eastBaseCenter + const Offset(10, 25));
  }

  void _label(
    Canvas canvas,
    String text,
    Offset offset, {
    Color color = _outline,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: color,
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant _HouseDiagramPainter oldDelegate) {
    return shadingEnabled != oldDelegate.shadingEnabled ||
        overhangDepth != oldDelegate.overhangDepth ||
        globalWindowArea != oldDelegate.globalWindowArea ||
        wallRValue != oldDelegate.wallRValue;
  }
}

// ---------------------------------------------------------
// CONTINUOUS CONTOUR HEATMAP WIDGET (Stateful API-Driven)
// ---------------------------------------------------------
class ContourHeatmap extends StatefulWidget {
  final String xAxisLabel;
  final String yAxisLabel;
  final String activeMetric;

  final double baseWallR;
  final double baseGlobalWindowArea;
  final double baseOverhang;
  final double baseVentilation;
  final bool shadingEnabled;
  final String scenario;

  final double currentX;
  final double currentY;
  final double minX;
  final double maxX;
  final double minY;
  final double maxY;

  const ContourHeatmap({
    super.key,
    required this.xAxisLabel,
    required this.yAxisLabel,
    required this.activeMetric,
    required this.baseWallR,
    required this.baseGlobalWindowArea,
    required this.baseOverhang,
    required this.baseVentilation,
    required this.shadingEnabled,
    required this.scenario,
    required this.currentX,
    required this.currentY,
    required this.minX,
    required this.maxX,
    required this.minY,
    required this.maxY,
  });

  @override
  State<ContourHeatmap> createState() => _ContourHeatmapState();
}

class _ContourHeatmapState extends State<ContourHeatmap> {
  bool isGenerating = false;
  List<List<double>>? coolingMatrix;
  List<List<double>>? heatingMatrix;
  Map<String, List<double>> globalBounds = {
    'cooling': [0, 100],
    'heating': [0, 100],
  };

  @override
  void initState() {
    super.initState();
    _fetchHeatmapData();
  }

  @override
  void didUpdateWidget(covariant ContourHeatmap oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.xAxisLabel != widget.xAxisLabel ||
        oldWidget.yAxisLabel != widget.yAxisLabel ||
        oldWidget.baseWallR != widget.baseWallR ||
        oldWidget.baseGlobalWindowArea != widget.baseGlobalWindowArea ||
        oldWidget.baseOverhang != widget.baseOverhang ||
        oldWidget.baseVentilation != widget.baseVentilation ||
        oldWidget.shadingEnabled != widget.shadingEnabled ||
        oldWidget.scenario != widget.scenario) {
      _fetchHeatmapData();
    }
  }

  Future<void> _fetchHeatmapData() async {
    setState(() => isGenerating = true);
    try {
      final response = await http.post(
        Uri.parse('http://127.0.0.1:8000/api/heatmap'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          "wall_r": widget.baseWallR,
          "global_window_area": widget.baseGlobalWindowArea,
          "overhang_depth": widget.baseOverhang,
          "vent_max_ach": widget.baseVentilation,
          "external_shading_enabled": widget.shadingEnabled,
          "weather_case": widget.scenario,
          "x_axis": widget.xAxisLabel,
          "y_axis": widget.yAxisLabel,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          coolingMatrix = List<List<double>>.from(
            data['cooling'].map((x) => List<double>.from(x)),
          );
          heatingMatrix = List<List<double>>.from(
            data['heating'].map((x) => List<double>.from(x)),
          );
          globalBounds['cooling'] = List<double>.from(
            data['bounds']['cooling'],
          );
          globalBounds['heating'] = List<double>.from(
            data['bounds']['heating'],
          );
        });
      }
    } catch (e) {
      debugPrint("Heatmap Error: $e");
    } finally {
      setState(() => isGenerating = false);
    }
  }

  String _getParamFriendlyName(String param) {
    switch (param) {
      case 'wallR':
        return 'Wall R-Value (m²K/W)';
      case 'globalWindowArea':
        return 'Global Window Area (m²)';
      case 'overhang':
        return 'Overhang Depth (m)';
      case 'ventilation':
        return 'Night Vent (ACH)';
      default:
        return param;
    }
  }

  @override
  Widget build(BuildContext context) {
    final activeMatrix = widget.activeMetric == 'cooling'
        ? coolingMatrix
        : heatingMatrix;
    final activeBounds = widget.activeMetric == 'cooling'
        ? globalBounds['cooling']!
        : globalBounds['heating']!;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              RotatedBox(
                quarterTurns: 3,
                child: Text(
                  _getParamFriendlyName(widget.yAxisLabel),
                  style: const TextStyle(
                    color: Colors.grey,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.grey.shade400, width: 1.5),
                  ),
                  child: isGenerating || activeMatrix == null
                      ? const Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              CircularProgressIndicator(),
                              SizedBox(height: 16),
                              Text(
                                "Loading heatmap data...",
                                style: TextStyle(color: Colors.grey),
                              ),
                            ],
                          ),
                        )
                      : CustomPaint(
                          painter: ContourPainter(
                            matrix: activeMatrix,
                            globalMin: activeBounds[0],
                            globalMax: activeBounds[1],
                            currentX: widget.currentX,
                            currentY: widget.currentY,
                            minX: widget.minX,
                            maxX: widget.maxX,
                            minY: widget.minY,
                            maxY: widget.maxY,
                          ),
                        ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Text(
          _getParamFriendlyName(widget.xAxisLabel),
          style: const TextStyle(
            color: Colors.grey,
            fontWeight: FontWeight.bold,
          ),
          textAlign: TextAlign.center,
        ),

        // DYNAMIC GRADIENT LEGEND
        const SizedBox(height: 12),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              '${activeBounds[0].toStringAsFixed(0)} kWh',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
            ),
            const SizedBox(width: 8),
            Container(
              width: 200,
              height: 14,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey.shade400),
                gradient: LinearGradient(
                  colors: [Colors.yellow.shade100, Colors.red],
                ),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '${activeBounds[1].toStringAsFixed(0)} kWh',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ],
    );
  }
}

class ContourPainter extends CustomPainter {
  final List<List<double>> matrix;
  final double globalMin;
  final double globalMax;
  final double currentX;
  final double currentY;
  final double minX;
  final double maxX;
  final double minY;
  final double maxY;

  ContourPainter({
    required this.matrix,
    required this.globalMin,
    required this.globalMax,
    required this.currentX,
    required this.currentY,
    required this.minX,
    required this.maxX,
    required this.minY,
    required this.maxY,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (matrix.isEmpty || matrix[0].isEmpty) return;

    int resX = matrix.length;
    int resY = matrix[0].length;

    double cellWidth = size.width / resX;
    double cellHeight = size.height / resY;

    double safeMax = globalMax == globalMin ? globalMin + 1 : globalMax;

    for (int x = 0; x < resX; x++) {
      for (int y = 0; y < resY; y++) {
        double val = matrix[x][y];
        double normalized = ((val - globalMin) / (safeMax - globalMin)).clamp(
          0.0,
          1.0,
        );

        Color cellColor =
            Color.lerp(Colors.yellow.shade100, Colors.red, normalized) ??
            Colors.red;
        final paint = Paint()
          ..color = cellColor
          ..style = PaintingStyle.fill;

        canvas.drawRect(
          Rect.fromLTWH(
            x * cellWidth,
            size.height - ((y + 1) * cellHeight),
            cellWidth + 1,
            cellHeight + 1,
          ),
          paint,
        );
      }
    }

    double normalizedCursorX = ((currentX - minX) / (maxX - minX)).clamp(
      0.0,
      1.0,
    );
    double normalizedCursorY = ((currentY - minY) / (maxY - minY)).clamp(
      0.0,
      1.0,
    );

    double pixelX = normalizedCursorX * size.width;
    double pixelY = size.height - (normalizedCursorY * size.height);

    canvas.drawCircle(Offset(pixelX, pixelY), 8, Paint()..color = Colors.black);
    canvas.drawCircle(Offset(pixelX, pixelY), 5, Paint()..color = Colors.white);

    final textPainter = TextPainter(
      text: const TextSpan(
        text: 'Current',
        style: TextStyle(
          color: Colors.black87,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    textPainter.layout();
    textPainter.paint(
      canvas,
      Offset(pixelX - (textPainter.width / 2), pixelY - 24),
    );
  }

  @override
  bool shouldRepaint(covariant ContourPainter oldDelegate) {
    return oldDelegate.currentX != currentX ||
        oldDelegate.currentY != currentY ||
        oldDelegate.matrix != matrix ||
        oldDelegate.globalMin != globalMin;
  }
}
