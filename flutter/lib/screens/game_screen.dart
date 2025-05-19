// lib/screens/game_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../providers/game_provider.dart';
import '../services/api_service.dart';
import 'results_screen.dart';
import 'reward_panel.dart';

class GameScreen extends StatefulWidget {
  final String gameId;
  final String token;
  const GameScreen({super.key, required this.gameId, required this.token});

  @override
  State<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends State<GameScreen> {
  late WebSocketChannel _channel;
  final ApiService _apiService = ApiService();
  bool _isSending = false;
  final int boardSize = 15;
  List<List<Map<String, dynamic>>> board = [];
  List<String> playerLetters = [];
  List<Map<String, dynamic>> placedTiles = [];
  int previewScore = 0;
  bool? isValidWord;
  Map<String, int> scores = {"player1": 0, "player2": 0};
  String currentTurn = "";
  String playerId = ""; // "player1" or "player2" tespit edilebilir
  int timeLeft = 0;
  List<String> availableRewards = [];
  String regionBlock = "";
  Map<String, List<String>> frozenLetters = {"player1":[],"player2":[]};

  @override
  void initState() {
    super.initState();
    _connectWebSocket();
    _fetchGameData();
  }

  void _connectWebSocket() {
    final wsUrl = "ws://10.0.2.2:8000/ws/game/${widget.gameId}";
    _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
    _channel.stream.listen((data) {
      try {
        final parsed = jsonDecode(data);
        // Gelen WebSocket mesajları
        // Örn: Rakibin hamlesi bitti, board güncellemesi vb.
        print("WS data: $parsed");
        // Gerçek bir senkronizasyon için fetchGameData yapabiliriz
        _fetchGameData();
      } catch (e) {
        print("WS parse error: $e");
      }
    }, onError: (err) {
      print("WS hata: $err");
    }, onDone: () {
      print("WS bağlantısı kapandı.");
    });
  }

  Future<void> _fetchGameData() async {
    // Biten oyun mu aktif mi vs. Kendi durumumuzu çekmek için, normalde /game detay endpoint'i yazabilirdik.
    // Burada basitce /list/active ve /list/finished taraması yaparak bu game'i bulabiliriz.
    final active = await _apiService.fetchActiveGames(widget.token);
    final finished = await _apiService.fetchFinishedGames(widget.token);

    bool found = false;
    for (var g in active) {
      if (g["game_id"] == widget.gameId) {
        // game active
        found = true;
        setState(() {
          scores = Map<String,int>.from(g["scores"]);
          currentTurn = g["turn"];
          timeLeft = g["time_left"];
        });
        break;
      }
    }
    if (!found) {
      for (var g in finished) {
        if (g["game_id"] == widget.gameId) {
          // game finished => go to results
          if (!mounted) return;
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => ResultsScreen(gameId: widget.gameId, token: widget.token),
            ),
          );
          return;
        }
      }
    }

    // Mevcut ham oyun verisi (detaylı) getirebileceğimiz ek bir endpoint yoksa,
    // test amaçlı "move" esnasında partial veriler...
    // Fakat tam senkron için endpoint ekleyebilirsiniz (örn. /game/detail/{id}).
    // Şimdilik playerLetters, board vs. local demo / partial logic ile
    // ya da passMove / confirmMove sonrasında da get
    // Burada demo veriler:
    // Board'ı dolduran bir endpoint de yok. Varsayalım local kalıyor.
    // (Gerçek projede /game/detail yapıp oradan board, hands, regionBlock vb. güncellemek gerek.)
    // Sadece availableRewards ve frozenLetters'ı da oradan alırız.
    // Şu an basit bir varsayım yapıyoruz.

    // Not: Gelişmiş senaryoda backend'e "/game/detail" ekleyip tam data almayı öneriyoruz.
    // Burada illüstrasyon olarak local update yapacağız.
  }

  @override
  void dispose() {
    _channel.sink.close();
    super.dispose();
  }

  void _calculatePreview() {
    final word = placedTiles.map((p) => p["letter"].toString()).join("");
    setState(() {
      previewScore = word.length * 10;
      isValidWord = word.length > 2;
    });
  }

  Color _wordColor() {
    if (isValidWord == null) return Colors.black;
    return isValidWord! ? Colors.green : Colors.red;
  }

  Widget _buildUpperInfo() {
    // Temsili scoreboard
    return Container(
      padding: const EdgeInsets.all(8),
      color: Colors.grey.shade300,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text("Oyuncu: $playerId", style: const TextStyle(fontWeight: FontWeight.bold)),
              Text("Puan: ${scores[playerId] ?? 0}"),
            ],
          ),
          Text("Kalan Harf: ??", style: const TextStyle(fontSize: 16)), // net data yok
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text("Rakip: ${playerId == "player1" ? "player2" : "player1"}", style: const TextStyle(fontWeight: FontWeight.bold)),
              Text("Puan: ${scores[playerId == "player1" ? "player2" : "player1"] ?? 0}"),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBoardCell(int row, int col) {
    // Demo: no real data from backend.
    return DragTarget<String>(
      builder: (ctx, candidateData, rejectedData) {
        return Container(
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey),
            color: Colors.white,
          ),
          alignment: Alignment.center,
          child: Text("$row,$col", style: const TextStyle(fontSize: 8)),
        );
      },
      onWillAccept: (draggedLetter) {
        // region block check
        // freeze check
        return true;
      },
      onAccept: (draggedLetter) {
        setState(() {
          placedTiles.add({"row": row, "col": col, "letter": draggedLetter});
          playerLetters.remove(draggedLetter);
          _calculatePreview();
        });
      },
    );
  }

  Widget _buildBoard() {
    return GridView.builder(
      itemCount: boardSize * boardSize,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: boardSize),
      itemBuilder: (ctx, index) {
        final r = index ~/ boardSize;
        final c = index % boardSize;
        return _buildBoardCell(r, c);
      },
    );
  }

  Widget _buildLetterRack() {
    return Container(
      padding: const EdgeInsets.all(8),
      color: Colors.blueGrey.shade50,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: playerLetters.map((l) => Draggable<String>(
            data: l,
            feedback: _buildRackTile(l, isDragging: true),
            childWhenDragging: Opacity(
              opacity: 0.3,
              child: _buildRackTile(l),
            ),
            child: _buildRackTile(l),
          )).toList(),
        ),
      ),
    );
  }

  Widget _buildRackTile(String letter, {bool isDragging = false}) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 4),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: isDragging ? Colors.deepOrange.withOpacity(0.8) : Colors.deepOrange,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(letter, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
    );
  }

  Future<void> _onConfirmMove() async {
    if (placedTiles.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text("Tahtaya harf yerleştirmediniz!")));
      return;
    }
    setState(() => _isSending = true);

    final word = placedTiles.map((p) => p["letter"].toString()).join("");
    final positions = placedTiles.map((p) => [p["row"], p["col"]]).toList();
    final usedLetters = placedTiles.map((p) => p["letter"].toString()).toList();

    final moveData = {
      "move_type": "place_word",
      "word": word,
      "positions": positions,
      "used_letters": usedLetters,
    };

    final result = await _apiService.confirmMove(widget.token, widget.gameId, moveData);
    setState(() => _isSending = false);

    if (result != null && result["message"] != null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(result["message"].toString())));
      setState(() {
        placedTiles.clear();
        previewScore = 0;
        isValidWord = null;
      });
      if (result["notifications"] != null) {
        for (var note in result["notifications"]) {
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(note.toString())));
        }
      }
      // Oyun bitmişse result["score"] vs.
      // Tekrar game state fetch
      _fetchGameData();
      // WebSocket ile de rakibe haber gidecek
      _channel.sink.add(jsonEncode({"action":"refresh"}));
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text("Hamle başarısız.")));
      setState(() {
        for (var tile in placedTiles) {
          playerLetters.add(tile["letter"]);
        }
        placedTiles.clear();
        previewScore = 0;
        isValidWord = null;
      });
    }
  }

  Future<void> _onPassMove() async {
    setState(() => _isSending = true);
    final resp = await _apiService.passMove(widget.token, widget.gameId);
    setState(() => _isSending = false);
    if (resp != null && resp["message"] != null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(resp["message"].toString())));
      if (resp["message"].toString().contains("oyun bitti")) {
        // bitmiş olabilir
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => ResultsScreen(gameId: widget.gameId, token: widget.token),
          ),
        );
      } else {
        _fetchGameData();
        _channel.sink.add(jsonEncode({"action":"refresh"}));
      }
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text("Pas başarısız.")));
    }
  }

  Future<void> _onSurrender() async {
    setState(() => _isSending = true);
    final success = await _apiService.surrender(widget.token, widget.gameId);
    setState(() => _isSending = false);
    if (success) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text("Teslim oldunuz.")));
      Navigator.pushReplacement(
          context,
          MaterialPageRoute(
              builder: (_) => ResultsScreen(gameId: widget.gameId, token: widget.token)));
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text("Teslim olma başarısız.")));
    }
  }

  // ShiftLetter demo
  Future<void> _onShiftLetter() async {
    if (placedTiles.isNotEmpty) return;
    final moveData = {
      "move_type": "shift_letter",
      "from_pos": [7, 7],
      "to_pos": [7, 8]
    };
    setState(() => _isSending = true);
    final result = await _apiService.confirmMove(widget.token, widget.gameId, moveData);
    setState(() => _isSending = false);

    if (result != null && result["message"] != null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(result["message"].toString())));
      if (result["notifications"] != null) {
        for (var note in result["notifications"]) {
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(note.toString())));
        }
      }
      _fetchGameData();
      _channel.sink.add(jsonEncode({"action":"refresh"}));
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text("Shift başarısız.")));
    }
  }

  void _onRewardUsed() {
    // Ödül kullanıldıktan sonra game state yenilenmeli
    _fetchGameData();
    // Bilgi rakibe
    _channel.sink.add(jsonEncode({"action":"refresh"}));
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<GameProvider>(
      builder: (ctx, gameProvider, child) {
        return Scaffold(
          appBar: AppBar(title: Text("Oyun - ${widget.gameId.substring(0, 8)}")),
          body: Column(
            children: [
              _buildUpperInfo(),
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      _buildBoard(),
                      const SizedBox(height: 8),
                      if (placedTiles.isNotEmpty)
                        Text("Önizlenen Skor: $previewScore", style: TextStyle(fontSize: 16, color: _wordColor())),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          ElevatedButton(
                            onPressed: _isSending ? null : _onConfirmMove,
                            child: const Text("Onayla"),
                          ),
                          ElevatedButton(
                            onPressed: _isSending ? null : _onPassMove,
                            child: const Text("Pas"),
                          ),
                          ElevatedButton(
                            onPressed: _isSending ? null : _onSurrender,
                            child: const Text("Teslim"),
                          ),
                          ElevatedButton(
                            onPressed: _onShiftLetter,
                            child: const Text("Shift Letter"),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      // RewardPanel
                      RewardPanel(
                        token: widget.token,
                        gameId: widget.gameId,
                        rewards: availableRewards,
                        onRewardUsed: _onRewardUsed,
                      ),
                      const SizedBox(height: 8),
                    ],
                  ),
                ),
              ),
              _buildLetterRack(),
            ],
          ),
        );
      },
    );
  }
}
