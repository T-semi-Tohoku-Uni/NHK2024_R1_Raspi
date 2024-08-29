# NHK2024_R1_Raspi
R1のラズパイのプログラム

## 初期設定
ラズパイの電源供給時に`can_init.sh`を実行するように設定する.

## 実装内容
[コントローラー](https://github.com/T-semi-Tohoku-Uni/NHK2024_R1_Smartphone_Controller)と通信をして、R1のメインの動きを制御するプログラム. 

ラズパイに電源を入れたら実行してほしい & 後から手元のPCでもsshして実行しているログ（画面への出力）を確認したかったので、systemctlにtmuxを立ち上げてプログラムを実行するシェルスクリプトを作成した。（`start_tmux_session.sh`）

禁止制御の内容は[issus](https://github.com/T-semi-Tohoku-Uni/NHK2024_R1_Raspi/issues/6)に記載している。

CANを連続で送ると、たまに送られないことがあってので、謎の`time.sleep(0.01)`を入れてます。原因わかったら嬉しいな。