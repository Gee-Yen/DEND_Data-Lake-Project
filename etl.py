import configparser
from datetime import datetime
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col
from pyspark.sql.functions import year, month, dayofmonth, hour, weekofyear, date_format, dayofweek
from pyspark.sql.types import TimestampType
import time


config = configparser.ConfigParser()
config.read('dl.cfg')

os.environ['AWS_ACCESS_KEY_ID']=config.get('AWS','AWS_ACCESS_KEY_ID')
os.environ['AWS_SECRET_ACCESS_KEY']=config.get('AWS','AWS_SECRET_ACCESS_KEY')


def create_spark_session():
    """
    Creates an entry point to work with RDD, DF and Dataset.

    Parameters:
      N/A    

    Returns: 
      SparkSession's object spark.
    """
    spark = SparkSession \
        .builder \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:2.7.0") \
        .getOrCreate()
    spark.conf.set('mapreduce.fileoutputcommiter.algorithm.version', '2')
    return spark


def process_song_data(spark, input_data, output_data):
    """
    Reads the song json file and insert data to the respective columns in the songs and artist tables.
    
    Parameters:
      spark - SparkSession's object .
      input_data - path of the input file to read from.
      output_data = path of the output file to write to.
      
    Returns: None.
    """
    # get filepath to song data file
    # Taking subset of files due to it takes longer to store in S3
    song_data = os.path.join(input_data, 'song_data/A/A/*/*.json')
    
    #song_data = os.path.join(input_data, 'song_data/*/*/*/*.json')
    
    # read song data file
    df = spark.read.json(song_data)
    
    # create temporary view
    df.createOrReplaceTempView('songs')

    # extract columns to create songs table
    songs_table = spark.sql("""
    select s.song_id,
           s.title,
           s.artist_id,
           s.artist_name,
           s.year,
           s.duration
    FROM   songs s
    """)
    
    # write songs table to parquet files partitioned by year and artist
    songs_table.write.partitionBy('year','artist_name').mode('overwrite').parquet(output_data+'songs/songs_table.parquet')
    
    print('***** Completed writing songs table *****')

    # extract columns to create artists table
    artists_table = spark.sql("""
    SELECT DISTINCT s.artist_id,
           s.artist_name,
           s.artist_location,
           s.artist_latitude,
           s.artist_longitude
    FROM   songs s
    """)
    
    # write artists table to parquet files
    artists_table.write.mode('overwrite').parquet(output_data+'artists/artists_table.parquet')
    
    print('***** Completed writing artists table *****')


def process_log_data(spark, input_data, output_data):
    """
    Reads the log json file and insert data to the respective columns in the users and time tables.
    Insert records into the Songplays table
    
    Parameters:
      spark - SparkSession's object .
      input_data - path of the input file to read from.
      output_data - path of the output file to write to.
      
    Returns: None.
    """
    # get filepath to log data file
    log_data = os.path.join(input_data, 'log_data/2018/11/*.json')

    # read log data file
    df = spark.read.json(log_data)
    
    # filter by actions for song plays
    df = df.filter(df.page == 'NextSong')

    # create timestamp column from original timestamp column
    get_timestamp = udf(lambda x: datetime.fromtimestamp(x/1000.0), TimestampType())
    df = df.withColumn('timestamp', get_timestamp(df.ts))
    
    # create temporary view
    df.createOrReplaceTempView('logs')
    
    # extract columns for users table    
    users_table = spark.sql("""
    SELECT DISTINCT l.userId,
           l.firstName,
           l.lastName,
           l.gender,
           l.level
    FROM   logs l
    """)
    
    # write users table to parquet files
    users_table.write.mode('overwrite').parquet(output_data+'users/users_table.parquet')
    
    print('***** Completed writing users table *****')

    # create timestamp column from original timestamp column
    # get_timestamp = udf(lambda x: datetime.fromtimestamp(x/1000.0), TimestampType())
    # df = df.withColumn('timestamp', get_timestamp(df.ts))
    
    # create datetime column from original timestamp column
    # get_datetime = udf()
    # df = 
    
    # extract columns to create time table
    time_table = spark.sql("""
    SELECT DISTINCT l.timestamp start_time,
           hour(l.timestamp) hour,
           dayofmonth(l.timestamp) dayofmonth,
           weekofyear(l.timestamp) weekofyear,
           year(l.timestamp) year,
           month(l.timestamp) month,
           dayofweek(l.timestamp) dayofweek
    FROM   logs l
    """)
    
    # write time table to parquet files partitioned by year and month
    time_table.write.partitionBy('year','month').mode('overwrite').parquet(output_data+'time/time_table.parquet')
    
    print('***** Completed writing time table *****')

    # read in song data to use for songplays table
    # Taking subset of files due to it takes longer to store in S3
    song_df = spark.read.json(os.path.join(input_data, 'song_data/A/A/*/*.json'))
    
    #song_df = spark.read.json(os.path.join(input_data, 'song_data/*/*/*/*.json'))
    # create temporary view
    song_df.createOrReplaceTempView('songs')

    # extract columns from joined song and log datasets to create songplays table 
    songplays_table = spark.sql("""
    SELECT row_number() OVER (PARTITION BY '' ORDER BY '') songplay_id,
           l.timestamp start_time,
           l.userId,
           l.level,
           s.song_id,
           s.artist_id,
           l.sessionId,
           l.location,
           l.userAgent,
           year(l.timestamp) year,
           month(l.timestamp) month
    FROM   logs l
    JOIN   songs s
    ON     l.artist = s.artist_name
    AND    l.song   = s.title
    AND    l.length = s.duration
    """)

    # write songplays table to parquet files partitioned by year and month
    songplays_table.write.partitionBy('year','month').mode('overwrite').parquet(output_data+'songplays/songplays_table.parquet')
    
    print('***** Completed writing songplays table *****')


def main():
    """
    Create spark session, reads data from S3, processes that data using Spark
    and writes them back to S3
    """
    main_start_time = time.time()
    
    spark_start_time = time.time()
    spark = create_spark_session()
    print('\n***** Create spark session took {0:.2f} seconds. ******\n'.format(time.time()-spark_start_time))
    
    input_data = "s3a://udacity-dend/"
    
    #Writing the resultsets to the local drive
    #output_data = "./result/"
    
    #Writing the resultsets to S3
    output_data = 's3a://mydlakebucket/'
    
    song_data_start_time = time.time()
    process_song_data(spark, input_data, output_data)    
    print('***** Process song data took {0:.2f} seconds. ******\n'.format(time.time()-song_data_start_time))
    
    log_data_start_time = time.time()
    process_log_data(spark, input_data, output_data)
    print('***** Process log data took {0:.2f} seconds. ******\n'.format(time.time()-log_data_start_time))
    
    print('***** Overall process took {0:.2f} seconds. ******\n'.format(time.time()-main_start_time))


if __name__ == "__main__":
    main()
