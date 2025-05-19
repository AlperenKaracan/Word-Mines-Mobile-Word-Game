// lib/models/game_model.dart

class GameModel {
  String gameId;
  List<List<Map<String, dynamic>>> board;
  Map<String, List<String>> hands;
  List<String> pool;
  Map<String, int> scores;
  String turn;
  int timeLeft;
  double successRate;
  String status;
  String? winner;
  Map<String, List<String>> availableRewards;
  Map<String, List<String>> frozenLetters;
  String? regionBlock;
  bool extraMoveInProgress;

  GameModel({
    required this.gameId,
    required this.board,
    required this.hands,
    required this.pool,
    required this.scores,
    required this.turn,
    required this.timeLeft,
    required this.status,
    this.winner,
    this.successRate = 0.0,
    required this.availableRewards,
    required this.frozenLetters,
    this.regionBlock,
    this.extraMoveInProgress = false,
  });

  factory GameModel.fromJson(Map<String, dynamic> json) {
    return GameModel(
      gameId: json['game_id'] ?? '',
      board: (json['board'] as List)
          .map((row) => (row as List).map((cell) => Map<String, dynamic>.from(cell as Map)).toList())
          .toList(),
      hands: Map<String, List<String>>.from(json['hands'] ?? {}),
      pool: List<String>.from(json['pool'] ?? []),
      scores: Map<String, int>.from(json['scores'] ?? {"player1": 0, "player2": 0}),
      turn: json['turn'] ?? '',
      timeLeft: json['time_left'] ?? 0,
      status: json['status'] ?? 'active',
      winner: json['winner'],
      successRate: (json['success_rate'] ?? 0.0).toDouble(),
      availableRewards: json['available_rewards'] != null
          ? Map<String, List<String>>.from(
          (json['available_rewards'] as Map).map((k,v) => MapEntry(k, List<String>.from(v))))
          : {"player1":[],"player2":[]},
      frozenLetters: json['frozen_letters'] != null
          ? Map<String, List<String>>.from(
          (json['frozen_letters'] as Map).map((k,v) => MapEntry(k, List<String>.from(v))))
          : {"player1":[],"player2":[]},
      regionBlock: json['region_block'],
      extraMoveInProgress: json['extra_move_in_progress'] ?? false,
    );
  }
}
