# -*- coding: utf-8 -*-
"""Model_RL_dose.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1nXVf74-_DAns3Jr5EamiYdSepwpsWV9k
"""

pip install gymnasium stable-baselines3 numpy



"""### the last edit now !"""

!pip install 'shimmy>=0.2.1'
!pip install stable-baselines3 gym gymnasium

!pip install gymnasium[monitoring]
!pip install stable-baselines3

import gym
from gym import spaces
import numpy as np
import matplotlib.pyplot as plt
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.vec_env import VecNormalize
from stable_baselines3.common.callbacks import EvalCallback

class AnesthesiaEnv(gym.Env):
    def __init__(self):
        super(AnesthesiaEnv, self).__init__()
        self.action_space = spaces.Box(low=np.array([1.0, 4.0]), high=np.array([3.5, 12.0]), dtype=np.float32)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(3,), dtype=np.float32)
        self.state = None
        self.correct_doses = [3.0, 8.0]
        self.rewards = []
        self.episode_length = 10
        self.current_step = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.state = self.generate_random_state()
        self.current_step = 0
        return self.state, {}

    def step(self, action):
        self.current_step += 1
        initial_dose, maintenance_dose, total_maintenance_dose = self.calculate_doses(action)
        reward = self.calculate_reward(action)
        done = self.current_step >= self.episode_length
        self.rewards.append(reward)
        return self.state, reward, done, False, {}

    def generate_random_state(self):
        weight = np.random.uniform(50, 100) / 100
        operation_duration = np.random.uniform(1, 6) / 6
        age = np.random.uniform(18, 70) / 70
        return np.array([weight, operation_duration, age], dtype=np.float32)

    def calculate_doses(self, action):
        induction_dose_rate, maintenance_infusion_rate = action
        weight = self.state[0] * 100
        age = self.state[2] * 70
        duration = self.state[1] * 6

        induction_dose_rate *= 0.75 if age > 65 else 1.0
        initial_dose = induction_dose_rate * weight
        maintenance_dose = (maintenance_infusion_rate * weight / 1000) * 60
        total_maintenance_dose = maintenance_dose * duration
        return initial_dose, maintenance_dose, total_maintenance_dose

    def calculate_reward(self, action):
        target_initial, target_maintenance = self.correct_doses
        initial_dose, maintenance_dose, _ = self.calculate_doses(action)

        error_initial = abs(initial_dose - target_initial)
        error_maintenance = abs(maintenance_dose - target_maintenance)

        weight_initial = 1.5 if initial_dose > target_initial else 1.0
        weight_maintenance = 1.5 if maintenance_dose > target_maintenance else 1.0

        weighted_error_initial = weight_initial * error_initial
        weighted_error_maintenance = weight_maintenance * error_maintenance

        reward = - (weighted_error_initial + weighted_error_maintenance)

        return reward

    def provide_doctor_feedback(self, approval, correct_doses):
        if not approval:
            self.correct_doses = correct_doses
        self.state = np.append(self.state[:-1], approval)

    def plot_rewards(self):
        plt.plot(self.rewards)
        plt.xlabel('Episode')
        plt.ylabel('Reward')
        plt.title('Reward Function Over Time')
        plt.show()

if __name__ == "__main__":
    env = DummyVecEnv([lambda: AnesthesiaEnv()])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.)

    eval_callback = EvalCallback(env, best_model_save_path='./logs/', log_path='./logs/', eval_freq=500, deterministic=True, render=False)
    # Check if model already exists, load if it does, otherwise train a new one
    try:
        model = PPO.load("ppo_anesthesia", env=env) # Pass the environment to the load function
        print("Loaded existing model.")
    except FileNotFoundError:
        model = PPO("MlpPolicy", env, verbose=1, learning_rate=0.00001, n_steps=2048, batch_size=128, n_epochs=10, clip_range=0.2)
        model.learn(total_timesteps=50000, callback=eval_callback)
        model.save("ppo_anesthesia")
        print("Trained a new model and saved it.")

    feedback_data = []

    while True:
        weight = float(input("Enter the patient's weight (kg): "))
        operation_duration = float(input("Enter the operation duration (hours): "))
        age = int(input("Enter the patient's age: "))

        normalized_state = np.array([weight / 100, operation_duration / 6, age / 70], dtype=np.float32)
        obs = env.reset()
        env.envs[0].state = normalized_state

        action, _ = model.predict(np.expand_dims(normalized_state, axis=0))
        action = action[0]

        initial_dose, maintenance_dose, total_maintenance_dose = env.envs[0].calculate_doses(action)
        print(f"Proposed induction dose rate: {action[0]:.2f} mg/kg")
        print(f"Proposed maintenance infusion rate: {action[1]:.2f} µg/kg/min")

        doctor_approval = input("Are these doses correct? (yes/no): ").strip().lower() == 'yes'
        if not doctor_approval:
            correct_bolus_dose = float(input("Enter the correct initial bolus dose (mg/kg): "))
            correct_infusion_rate = float(input("Enter the correct maintenance infusion rate (µg/kg/min): "))
            correct_doses = [correct_bolus_dose, correct_infusion_rate]
            env.envs[0].provide_doctor_feedback(False, correct_doses)
            feedback_data.append((normalized_state, correct_doses))
        else:
            correct_doses = action
            env.envs[0].provide_doctor_feedback(True, action)

        print(f"correct_bolus_dose by dr : {correct_doses[0]:.2f} mg/kg")
        print(f"correct_infusion_rate by dr : {correct_doses[1]:.2f} µg/kg/min")

        final_initial_dose = correct_doses[0] * weight if not doctor_approval else initial_dose
        final_maintenance_dose = (correct_doses[1] * weight / 1000) * 60 if not doctor_approval else maintenance_dose
        final_total_maintenance_dose = final_maintenance_dose * operation_duration

        print(f"Final initial dose: {final_initial_dose:.2f} mg")
        print(f"Final maintenance dose: {final_maintenance_dose:.2f} mg/hr")
        print(f"Total maintenance dose: {final_total_maintenance_dose:.2f} mg/hr")

        reward = env.envs[0].calculate_reward(action)
        print(f"Reward: {reward:.2f}")

        # Retrain model with feedback in real-time
        if not doctor_approval:
            env.envs[0].state = normalized_state
            correct_action = np.array(correct_doses, dtype=np.float32)
            model.learn(total_timesteps=1000, log_interval=4, reset_num_timesteps=False, tb_log_name="fine_tune")
            print("Model updated with doctor feedback.")


        continue_training = input("Do you want to continue with another patient? (yes/no): ").strip().lower() == 'yes'
        if not continue_training:
            break


    # Save the fine-tuned model
    model.save("ppo_anesthesia_finetuned")

