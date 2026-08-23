from aug9.core.database import initialise_database
from aug9.core.agent import run_aug9


def main():

    initialise_database()

    user_input = input(
        "Aug9 > "
    )

    response = run_aug9(
        user_input
    )

    print()
    print(response)


if __name__ == "__main__":
    main()
