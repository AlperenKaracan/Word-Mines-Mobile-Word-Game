// lib/providers/game_provider.dart
import 'dart:async';
import 'package:flutter/material.dart';
import '../models/game_model.dart';

class GameProvider extends ChangeNotifier {
  GameModel? _currentGame;
  Timer? _timer;

  GameModel? get currentGame => _currentGame;

  void setCurrentGame(GameModel gm) {
    _currentGame = gm;
    notifyListeners();
  }

  void startTimer(int seconds) {
    _timer?.cancel();
    int sec = seconds;
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (sec > 0) {
        sec--;
        if (_currentGame != null) {
          _currentGame!.timeLeft = sec;
          notifyListeners();
        }
      } else {
        timer.cancel();
      }
    });
  }

  void cancelTimer() {
    _timer?.cancel();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
